from ncs_udm import UDM
import DCC_api, json, csv, time, os, sys

class DCC_Model(UDM):
    def __init__(self):
        super().__init__()
        self.csv_config_list = list()
        self.current_point_value = dict()
        with open(self.config_path) as config_flie:
            self.current_config = json.load(config_flie)
        DCC_api.Main = self.Main
        DCC_api.desigo_ip = self.current_config['udm']['desigo_host']
        DCC_api.desigo_username = self.current_config['udm']['desigo_username']
        DCC_api.desigo_password = self.current_config['udm']['desigo_password']
        self.udm_id = self.current_config['udm']['id']
        self.data_ver = self.current_config['ver']
        self.alarm_point = self.current_config['udm']['alarm_point']
        
        self.get_point_url = self.current_config['udm']['get_url']['bacnet_point_information'].replace("desigo_ip", DCC_api.desigo_ip)
        self.events_list_url = self.current_config['udm']['get_url']['events_list'].replace("desigo_ip", DCC_api.desigo_ip)
        self.point_list_value_url = self.current_config['udm']['post_url']['point_list_value'].replace("desigo_ip", DCC_api.desigo_ip)
        self.change_value_url = self.current_config['udm']['post_url']['change_value'].replace("desigo_ip", DCC_api.desigo_ip)
        self.close_alarm_url_type = self.current_config['udm']['post_url']['close_alarm'].replace("desigo_ip", DCC_api.desigo_ip)
    
    def check_dcc_ip(self):
        try:
            DCC_api.check_ip()
        except:
            self.Main.error("Connection Error!!!")
            os.execv(sys.executable, ['python'] + sys.argv)
    
    def create_token_file(self):
        try:
            if os.path.isfile('./login_token.txt'):
                if os.path.getsize("./login_token.txt") != 0:
                    with open("./login_token.txt", "r+") as token_file:
                        del_token = token_file.read()
                        DCC_api.delete_token(del_token)
                    with open("./login_token.txt", "a") as token_file:
                        token_file.truncate(0)
            else:
                open("login_token.txt", "x")
            get_token = DCC_api.get_token()
            if get_token.status_code == 200:
                self.token = get_token.json()["access_token"]
                with open("login_token.txt", "a+") as token_file:
                    token_file.write(self.token)
            else:
                self.Main.error("Get Token Fail")
        except:
            self.Main.error(""'"create_token_file"'" have error.", exc_info = True)
    
    def create_config_csv(self):
        response = DCC_api.get(self.token, self.get_point_url)
        if response.status_code == 200:
            point_list = response.json()
        with open('config/config.csv', 'w', newline='') as csvFile:
            writer = csv.DictWriter(csvFile, ["Name","ObjectID","FunID(hex.xxxx)","DataType","Type(0~2:R、W、R/W)","Unit","range","setrange","tag"])
            writer.writeheader()
            for count, point_content in enumerate(point_list):
                writer.writerow({"Name": point_content['Descriptor'], "ObjectID": point_content['ObjectId'], "FunID(hex.xxxx)": f"{'%04x' %count}", "Type(0~2:R、W、R/W)": 2})
                if point_content['Name'] in self.alarm_point:
                    writer.writerow({"Name": f"{point_content['Name']}_告警", "ObjectID": point_content['ObjectId'], "FunID(hex.xxxx)": f"{'%04x' %count}_alarm", "Type(0~2:R、W、R/W)": 2, "setrange": [{'0': 'Off', '2': 'On/Alarm', '3': 'High Limit', '4': 'Low Limit'}]})
        with open('config/config.csv', newline='',) as point_config_file:
            csv_to_dict = csv.DictReader(point_config_file)
            for dict_count in csv_to_dict:
                self.csv_config_list.append(dict_count)
    
    def change_detect(self):
        try:
            command_point_list = list()
            check_point_value = dict()
            change_data_list = list()
            for point_dict in self.csv_config_list:
                if "alarm" in point_dict['FunID(hex.xxxx)']:
                    command_point_list.append(f"{point_dict['ObjectID']}.Event_State")
                else:
                    command_point_list.append(f"{point_dict['ObjectID']}.Present_Value")
            response = DCC_api.post(self.token, self.point_list_value_url, json.dumps(command_point_list))
            if response.status_code == 200:
                response_list = response.json()
                for count, point_response_count in enumerate(response_list):
                    if point_response_count['ErrorCode'] == 0:
                        value = point_response_count['Value']['Value']
                    elif point_response_count['ErrorCode'] == 525:
                        value = 'None'
                    check_point_value[self.csv_config_list[count]['FunID(hex.xxxx)']] = value
                if self.current_point_value != check_point_value:
                    for point_dict in self.csv_config_list:
                        if self.current_point_value[point_dict['FunID(hex.xxxx)']] != check_point_value[point_dict['FunID(hex.xxxx)']]:
                            change_data_list.append(f"UDM|{self.udm_id}|{point_dict['FunID(hex.xxxx)']}|{check_point_value[point_dict['FunID(hex.xxxx)']]}|{int(time.time()*1000)}")
                    self.current_point_value = check_point_value
                if change_data_list:
                    return change_data_list
            else:
                self.Main.info("Reget Desigo CC Token")
                os.execv(sys.executable, ['python'] + sys.argv)
        except:
            self.Main.error(""'"state_change"'" have error.", exc_info = True)
    
    def register_config(self):
        try:
            payload_data_dict = dict()
            payload_fun_data_list = list()
            for point_dict in self.csv_config_list:
                if 'alarm' in point_dict['FunID(hex.xxxx)']:
                    payload_data_dict['id'] = point_dict['FunID(hex.xxxx)']
                    payload_data_dict['name'] = point_dict['Name']
                    payload_data_dict['type'] = point_dict['Type(0~2:R、W、R/W)']
                    payload_data_dict['setrange'] = point_dict['setrange']
                    payload_fun_data_list.append(payload_data_dict)
                    payload_data_dict = {}
                else:
                    payload_data_dict['id'] = point_dict['FunID(hex.xxxx)']
                    payload_data_dict['name'] = point_dict['Name']
                    payload_data_dict['type'] = point_dict['Type(0~2:R、W、R/W)']
                    payload_fun_data_list.append(payload_data_dict)
                    payload_data_dict = {}
            return payload_fun_data_list
        except:
            self.Main.error(""'"register"'" have error.", exc_info = True)
    
    def make_config(self):
        try:
            payload_data_dict = dict()
            payload_fun_data_list = list()
            for point_dict in self.csv_config_list:
                if 'alarm' in point_dict['FunID(hex.xxxx)']:
                    payload_data_dict['id'] = point_dict['FunID(hex.xxxx)']
                    payload_data_dict['name'] = point_dict['Name']
                    payload_data_dict['type'] = point_dict['Type(0~2:R、W、R/W)']
                    payload_data_dict['setrange'] = point_dict['setrange']
                    payload_fun_data_list.append(payload_data_dict)
                    payload_data_dict = {}
                else:
                    payload_data_dict['id'] = point_dict['FunID(hex.xxxx)']
                    payload_data_dict['name'] = point_dict['Name']
                    payload_data_dict['type'] = point_dict['Type(0~2:R、W、R/W)']
                    payload_fun_data_list.append(payload_data_dict)
                    payload_data_dict = {}
            return payload_fun_data_list
        except:
            self.Main.error(""'"code1"'" have error.", exc_info = True)
    
    def make_status(self):
        try:
            command_point_list = list()
            payload_status_data_list = list()
            for point_dict in self.csv_config_list:
                if "alarm" in point_dict['FunID(hex.xxxx)']:
                    command_point_list.append(f"{point_dict['ObjectID']}.Event_State")
                else:
                    command_point_list.append(f"{point_dict['ObjectID']}.Present_Value")
            response = DCC_api.post(self.token, self.point_list_value_url, json.dumps(command_point_list))
            if response.status_code == 200:
                response_list = response.json()
                for count, point_response_count in enumerate(response_list):
                    if point_response_count['ErrorCode'] == 0:
                        value = point_response_count['Value']['Value']
                    elif point_response_count['ErrorCode'] == 525:
                        value = 'None'
                    payload_status_data_list.append(f"UDM|{self.udm_id}|{self.csv_config_list[count]['FunID(hex.xxxx)']}|{value}|{int(time.time()*1000)}")
                    self.current_point_value[self.csv_config_list[count]['FunID(hex.xxxx)']] = value
                return payload_status_data_list
            else:
                self.Main.info("Reget Desigo CC Token")
                os.execv(sys.executable, ['python'] + sys.argv)
        except:
            self.Main.error(""'"code2"'" have error.", exc_info = True)
    
    def exec_control(self, *code3_payload_list):
        try:
            command_count = int()
            for payload_command in code3_payload_list[0]:
                payload_command_list = payload_command.split("|")
                if payload_command_list[0] == "UDM" and int(payload_command_list[1]) == self.udm_id:
                    command_count += 1
                    for point_dict in self.csv_config_list:
                        if payload_command_list[2] == point_dict['FunID(hex.xxxx)']:
                            if 'alarm' in point_dict['FunID(hex.xxxx)']:
                                if payload_command_list[3] == "0":
                                    respond = DCC_api.get(self.token, self.events_list_url)
                                    for events_list in respond.json()['Events']:
                                        if events_list['State'] == 'Unprocessed':
                                            for commands_list in events_list['Commands']:
                                                if commands_list['Id'] == 'Ack':
                                                    close_alarm_url = self.close_alarm_url_type + commands_list['_links'][0]['Href']
                                                    respond = DCC_api.post(self.token, close_alarm_url, payload = None)
                                                    if respond.status_code == 200:
                                                        command_count -= 1
                                                    break
                            else:
                                post_url = self.change_value_url.replace("object_id", point_dict['ObjectID'])
                                change_value_body = [{"Name": "Value","DataType": "ExtendedReal","Value": f"{payload_command_list[3]}"}]
                                respond = DCC_api.post(self.token, post_url, json.dumps(change_value_body))
                                if respond.status_code == 200:
                                    command_count -= 1
                                break
            if command_count == 0:
                return 0
            else:
                return 1
        except:
            self.Main.error(""'"code3"'" have error.", exc_info = True)
    
    def exec_update(self):
        try:
            return 0
        except:
            self.Main.error(""'"code4"'" have error.", exc_info = True)

dcc_model = DCC_Model()
dcc_model.check_dcc_ip()
dcc_model.create_token_file()
dcc_model.create_config_csv()
dcc_model.start