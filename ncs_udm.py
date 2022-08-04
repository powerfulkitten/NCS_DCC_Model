from abc import ABC, abstractmethod
import json, os, time, random, string, sys
import logging, logging.handlers
import threading
import paho.mqtt.client as mqtt

class Repeating_Timer(threading.Timer):
    '''
    Remake Timer from threading Class 
    Make Timer can Repeating
    '''
    def __init__(self, interval, function, args=None, kwargs=None):
        threading.Thread.__init__(self)
        self.interval = interval
        self.function = function
        self.args = args if args is not None else []
        self.kwargs = kwargs if kwargs is not None else {}
        self.finished = threading.Event()
    
    def cancel(self):
        """Stop the timer if it hasn't finished yet."""
        self.finished.set()
    
    def run(self):
        while not self.finished.is_set():
            self.function(*self.args, **self.kwargs)
            self.finished.wait(self.interval)

class UDM(ABC):
    '''
    UDM module integrate Protocol to NCS those NCS does not have
    '''
    def __init__(self):
        '''
        Loading initialization parameter
        1.config_path : The file path about NCS connect information
        2.Main : System record log
        '''
        try:
            self.config_path = './config/config.json'
            self.Main = logging.getLogger('Main')
            self.Main.setLevel(min(logging.INFO, logging.INFO))
            log_fmt = logging.Formatter('%(asctime)s %(name)-10s %(levelname)-8s %(message)s', '%Y/%m/%d %H:%M:%S')
            if not os.path.isdir('./logs/'):
                os.mkdir('./logs/')
            
            file_handler = logging.handlers.TimedRotatingFileHandler('./logs/log.log',when='midnight',backupCount = 7)
            file_handler.suffix = "%Y-%m-%d.log"
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(log_fmt)
            self.Main.addHandler(file_handler)
            
            console = logging.StreamHandler()
            console.setLevel(logging.INFO)
            console.setFormatter(log_fmt)
            self.Main.addHandler(console)
        except:
            self.Main.error(""'"__init__"'" have error.", exc_info = True)
    
    def _random_string(self, length: int) -> str:
        '''
        Create specify length to using mqtt client id
        '''
        try:
            letters = string.ascii_letters
            result_str = ''.join(random.choice(letters) for i in range(length))
            return result_str
        except:
            self.Main.error(""'"random_string"'" have error.", exc_info = True)
    
    def _loading_ncs_config(self):
        '''
        NCS connect information
        Step.1 Check the path whether have file
        Step.2 Loading key value
        '''
        try:
            while True:
                if not os.path.isfile(self.config_path):
                    self.Main.error(f"Error!!! Not found config.json in path '{self.config_path}'")
                    time.sleep(2)
                else:
                    break
            with open(self.config_path) as config_flie:
                self.current_config = json.load(config_flie)
            self.ncs_id = self.current_config['ncs']['sid']
            self.module_name = self.current_config['ncs']['name']
            self.mqtt_host = self.current_config['ncs']['host']
            self.mqtt_port = self.current_config['ncs']['port']
            self.mqtt_regid = self.current_config['ncs']['regid']
            self.mqtt_pwd = self.current_config['ncs']['pwd']
            self.heartbeat_secnods = self.current_config['ncs']['heartbeat_secnods']
            self.polling_secnods = self.current_config['ncs']['polling_secnods']
        except:
            self.Main.error(""'"loading_ncs_config"'" have error.", exc_info = True)
            time.sleep(2)
            self._loading_ncs_config()
    
    def _init_timer(self):
        '''
        Create will be using Timer
        '''
        try:
            self.config_file_check_timer = Repeating_Timer(1, self._config_file_check)
            self.config_file_check_timer.setName("config file check")
            self.heartbeat_timer = Repeating_Timer(1, self._heartbeat)
            self.heartbeat_timer.setName("heartbeat")
            self.state_change_timer = Repeating_Timer(self.polling_secnods, self._status_change)
            self.state_change_timer.setName("state change")
        except:
            self.Main.error(""'"_init_timer"'" have error.", exc_info = True)
    
    def _config_file_check(self):
        '''
        If config content is changed system will restart
        '''
        try:
            with open(self.config_path) as config_flie:
                self.check_config = json.load(config_flie)
            if self.check_config != self.current_config:
                self.Main.info("Config file is updata")
                os.execv(sys.executable, ['python'] + sys.argv)
            if not self.config_file_check_timer.is_alive():
                self.config_file_check_timer.start()
        except:
            self.Main.error(""'"config_file_check"'" have error.", exc_info = True)
    
    def _start_mqtt_connect(self):
        '''
        Create mqtt connect information and run
        '''
        try:
            self.mqtt_client = mqtt.Client(client_id = self._random_string(16))
            self.mqtt_client.will_set(f"NCS/{self.ncs_id}/{self.mqtt_regid}", "offline", 0, False)
            self.mqtt_client.username_pw_set(self.mqtt_regid, self.mqtt_pwd)
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_message = self._on_message
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, 60)
            self.mqtt_client.loop_forever()
        except:
            self.Main.error(""'"start_mqtt_connect"'" have error.", exc_info = True)
    
    def _on_connect(self, client, userdata, flags, rc):
        '''
        When mqtt is connected will trigger
        '''
        try:
            if self.mqtt_client.is_connected():
                self.Main.info(f"MQTT > {self.mqtt_host} is connected")
                client.subscribe(f"UDM/{self.mqtt_regid}")
                self.heartbeat_last_time = int(time.time()*1000)
                self.ncs_connect_status = True
                self._register()
        except:
            self.Main.error(""'"_on_connect"'" have error.", exc_info = True)
    
    def _on_message(self, client, userdata, msg):
        '''
        When mqtt receive anything message will trigger
        '''
        try:
            control_code_dict = {
                    1: self._code1,
                    2: self._code2,
                    3: self._code3,
                    4: self._code4,
                    5: self._code5,
                    'offline': self._offline
                    }
            if msg:
                try:
                    message = json.loads(msg.payload.decode('utf-8'))
                    try:
                        payload_list = message["Payload"]["Actions"]
                    except:
                        pass
                    request_id = message["CID"]
                    result = control_code_dict[message["Code"]]
                    try:
                        result(request_id, payload_list)
                    except:
                        result(request_id)
                except:
                    message = msg.payload.decode('utf-8')
                    try:
                        result = control_code_dict.get(message)
                        result()
                    except:
                        self.Main.info(f"Recv > NCS({self.mqtt_host}) => UDM : Unknown Packet", exc_info = True)
        except:
            self.Main.error(""'"_on_message"'" have error.", exc_info = True)
    
    def _heartbeat(self):
        '''
        This function will automatically send heartbeat payload when
        UDM model a period of time not send to NCS
        '''
        try:
            Heartbeat_data = {
                    "ObjName": "UDM",
                    "TimeStamp": int(time.time()*1000),
                    "Status":[]
                }
            now_time = int(time.time()*1000)
            time_check = int((now_time - self.heartbeat_last_time)/1000)
            if time_check >= self.heartbeat_secnods:
                self._send('HeartBeat', self.ncs_id, Heartbeat_data)
        except:
            self.Main.error(""'"heartbeat"'" have error.", exc_info = True)
    
    def _register(self):
        '''
        When mqtt is connected UDM model will automatically
        send configuration data
        '''
        try:
            if not self.heartbeat_timer.is_alive():
                self.heartbeat_timer.start()
            register_data = {
                    "ObjName": "UDM",
                    "name": self.module_name,
                    "TimeStamp": int(time.time()*1000),
                    "ID": self.udm_id,
                    "ver": self.data_ver,           
                    "regid": self.mqtt_regid,
                    "status": 0, 
                    "Code": 101,
                    }
            register_data['funs'] = self.register_config()
            self._send("Register", self.ncs_id, register_data)
        except:
            self.Main.error(""'"_register"'" have error.", exc_info = True)
    
    def _code1(self, request_id, *code3_payload_list):
        '''
        When receive Code1 request UDM model will send configuration data
        '''
        try:
            if not self.config_file_check_timer.is_alive() and not self.heartbeat_timer.is_alive() and not self.state_change_timer.is_alive() and request_id == self.ncs_id:
                self.ncs_connect_status = True
                self._init_timer()
                self.config_file_check_timer.start()
                self.heartbeat_timer.start()
            self.Main.info(f"Recv > NCS({self.mqtt_host}) => UDM : Code1")
            code1_data = {
                    "ObjName": "UDM",
                    "name": self.module_name,
                    "TimeStamp": int(time.time()*1000),
                    "ID": self.udm_id,
                    "ver": self.data_ver,           
                    "regid": self.mqtt_regid,
                    "status": 0, 
                    "Code": 101,
                    }
            if self.ncs_connect_status:
                code1_data['funs'] = self.make_config()
            self._send('Code1', request_id, code1_data)
        except:
            self.Main.error(""'"_code1"'" have error.", exc_info = True)
    
    def _code2(self, request_id, *code3_payload_list):
        '''
        When receive Code2 request UDM model will send current status data
        and start detect status change
        '''
        try:
            self.Main.info(f"Recv > NCS({self.mqtt_host}) => UDM : Code2")
            code2_data = {
                        "ObjName": "UDM",
                        "TimeStamp": int(time.time()*1000),
                        "ID": self.udm_id,          
                        "status": 0,    
                        "Code": 102,
                        }
            if self.ncs_connect_status:
                code2_data['Status'] = self.make_status()
            self._send("Code2", request_id, code2_data)
            if not self.state_change_timer.is_alive() and self.ncs_connect_status:
                if not self.state_change_timer.finished.is_set():
                    self.state_change_timer.start()
        except:
            self.Main.error(""'"_code2"'" have error.", exc_info = True)
    
    def _code3(self, request_id, *code3_payload_list):
        '''
        When receive Code3 request UDM model will check this command control
        payload to change data value and send success or fail respond
        '''
        try:
            self.Main.info(f"Recv > NCS({self.mqtt_host}) => UDM : Code3")
            code3_data = {
                "ObjName": "UDM",
                "TimeStamp": int(time.time()*1000),
                "ID": self.udm_id,
                "Code": 103
                }
            if self.ncs_connect_status:
                code3_data['status'] = self.exec_control(code3_payload_list)
            self._send("Code3", request_id, code3_data)
        except:
            self.Main.error(""'"_code3"'" have error.", exc_info = True)
    
    def _code4(self, request_id, *code3_payload_list):
        '''
        When receive Code4 request UDM model will check this command control
        payload to update configuration data and send success or fail respond
        '''
        try:
            self.Main.info(f"Recv > NCS({self.mqtt_host}) => UDM : Code4")
            code4_data = {
                "ObjName": "UDM",
                "TimeStamp":int(time.time()*1000),
                "ID": self.udm_id,
                "Code":104
                }
            if self.ncs_connect_status:
                code4_data['status'] = self.exec_update()
            self._send("Code4", request_id, code4_data)
        except:
            self.Main.error(""'"_code4"'" have error.", exc_info = True)
    
    def _code5(self, request_id):
        for thread_name in threading.enumerate():
            print(thread_name)
    
    def _status_change(self):
        '''
        Follow parameter polling_seconds to detect data value whether change
        If data value is change will send status change notify to NCS
        '''
        try:
            status_change_data = {
                    "ObjName": "UDM",
                    "ID": self.udm_id,
                    "TimeStamp": int(time.time()*1000)
                    }
            change_data = self.change_detect()
            if change_data:
                status_change_data['Status'] = change_data
                self._send("State Change", self.ncs_id, status_change_data)
        except:
            self.Main.error(""'"_status_change"'" have error.", exc_info = True)
    
    def _offline(self):
        '''
        When receive offline, represent NCS is disconnect and can to do something
        '''
        try:
            self.Main.info(f"Recv > NCS({self.mqtt_host}) => UDM : offline")
            self.ncs_connect_status = False
            self.config_file_check_timer.cancel()
            self.heartbeat_timer.cancel()
            self.state_change_timer.cancel()
        except:
            self.Main.error(""'"_offline"'" have error.", exc_info = True)
    
    def _send(self, control_code, request_id, payload):
        '''
        Send payload message to specify mqtt topic
        '''
        try:
            if request_id == self.ncs_id:
                topic = f"NCS/{self.ncs_id}/{self.mqtt_regid}"
            else:
                topic = f"NCS/{request_id}/{self.mqtt_regid}"
            if self.ncs_connect_status:
                self.mqtt_client.publish(topic, json.dumps(payload))
                self.Main.info(f"Send > UDM => {topic} : {control_code}")
                self.heartbeat_last_time = int(time.time()*1000)
            else:
                self.Main.info(f"Send > UDM => {topic} : {control_code} (NCS offline)")
        except:
            self.Main.error(""'"_send"'" have error.", exc_info = True)
    
    '''
    abstractmethod : When some class inherit UDM need to create
    '''
    @abstractmethod
    def register_config(self):
        '''
        This abstract method will return register config payload
        configuration data type :
        [
            {
                "id": "1_di_1",
                "name": "DI_1",  //名稱 (唯一可以異動項目)
                "type": 0        // 0:r 1:w 2:r+w
            },
            {
                "id": "1_di_2",
                "name": "DI_2",
                "type": 0
            },
            {
                "id": "1_di_3",
                "name": "DI_3",
                "type": 0
            }
        ]
        '''
        pass
    
    @abstractmethod
    def make_config(self):
        '''
        This abstract method will return make config payload
        configuration data type :
        [
            {
                "id": "1_di_1",
                "name": "DI_1",  //名稱 (唯一可以異動項目)
                "type": 0        // 0:r 1:w 2:r+w
            },
            {
                "id": "1_di_2",
                "name": "DI_2",
                "type": 0
            },
            {
                "id": "1_di_3",
                "name": "DI_3",
                "type": 0
            }
        ]
        '''
        pass
    
    @abstractmethod
    def make_status(self):
        '''
        This abstract method will return make status payload
        current status data type :
        [
            "UDM|1|1_di_1|0|1628748845827",
            "UDM|1|1_di_2|0|1628748845827",
            "UDM|1|1_di_3|0|1628748845827",
            "UDM|1|1_di_4|0|1628748845827",
            "UDM|1|1_di_5|0|1628748845827",
            "UDM|1|1_di_6|0|1628748845827",
            "UDM|1|1_di_7|0|1628748845827",
            "UDM|1|1_di_8|0|1628748845827",
            "UDM|1|1_do_1|0|1628748845827",
            "UDM|1|1_do_2|0|1628748845827",
            "UDM|1|1_do_3|0|1628748845827",
            "UDM|1|1_do_4|0|1628748845827",
            "UDM|1|1_do_5|0|1628748845827",
            "UDM|1|1_do_6|0|1628748845827"
        ]
        '''
        pass
    
    @abstractmethod
    def exec_control(self, *code3_payload_list):
        '''
        This abstract method will return success or fail of the exec control
        success or fail respond :
        Success : 0
        Fail : 1
        '''
        pass
    
    @abstractmethod
    def exec_update(self):
        '''
        This abstract method will return success or fail of the exec update
        success or fail respond :
        Success : 0
        Fail : 1
        '''
        pass
    
    @abstractmethod
    def change_detect(self):
        '''
        Follow parameter polling_seconds to detect data value whether change
        If data value is change will send status change notify to NCS
        status change notify type :
        [
            "UDM|1|011|1|1627441665432", //{ObjName}|{ID}|{funID}|{value}|{最後異動時間}"
            "UDM|1|012|1|1627441665432",
        ]
        '''
        pass
    
    @property
    def start(self):
        '''
        Call this property to run the setup complete udm model
        '''
        try:
            self.Main.info('<<< Start >>>')
            self._loading_ncs_config()
            self._init_timer()
            self._config_file_check()
            self._start_mqtt_connect()
        except:
            self.Main.error(""'"start"'" have error.", exc_info = True)