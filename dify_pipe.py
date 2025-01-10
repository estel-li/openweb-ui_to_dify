"""
title: DIFY Manifold Pipe
authors: Estel
author_url: https://github.com/estel_li
funding_url: https://github.com/xuzhougeng
funding_url: https://github.com/open-webui
version: 0.1
description: 该流程用于DIFY的API接口，用于与DIFY的API进行交互
"""

import logging
import os
import requests
import json
import time
from typing import List, Union, Generator, Iterator, Optional
from pydantic import BaseModel, Field
from open_webui.utils.misc import pop_system_message
from open_webui.config import UPLOAD_DIR
import base64
import tempfile
from urllib.parse import quote
from io import BytesIO
#Debug模式
DEBUG_MODE = True
def get_file_extension(file_name: str) -> str:
    return os.path.splitext(file_name)[1].strip(".")

#从__event_emitter__中获取闭包变量
def get_closure_info(func):
    # 获取函数的闭包变量
    if hasattr(func, "__closure__") and func.__closure__:
        for cell in func.__closure__:
            if isinstance(cell.cell_contents, dict):
                return cell.cell_contents
    return None


class Pipe:
    class Valves(BaseModel):
        # 环境变量
        DIFY_BASE_URL: str = Field(default="http://192.168.1.4/v1")
        DIFY_KEY: str = Field(default="app-JLVIWnKKfGnoiJqCuD1GsYnR")
        FILE_SERVER: str = Field(default="http://192.168.1.4/v1/files/upload")
        DIFY_WORKFLOW: str = Field(default="Dify_API_GPT4o")
        DIFY_MODLE_ID: str = Field(default="dify_id")

    def __init__(self):
        self.type = "manifold"
        self.id = "dify"
        self.name = "dify/"
        self.chat_message_mapping = {}
        self.dify_chat_model = {}
        self.dify_file_list = {}
        self.data_cache_dir = "data/dify"
        self.load_state()
        self.valves = self.Valves()
                

    def save_state(self):
        """
        持久化Dify相关的状态变量到文件
        这个函数的主要作用是将程序运行时的状态信息保存到本地文件中，以便程序重启后能够恢复之前的状态
        """
        # 创建数据缓存目录，如果目录不存在则创建
        # exist_ok=True 表示如果目录已存在也不会报错
        os.makedirs(self.data_cache_dir, exist_ok=True)

        # 1. 保存聊天消息映射关系
        # chat_message_mapping.json 存储了聊天ID与DIFY消息ID的对应关系
        chat_mapping_file = os.path.join(
            self.data_cache_dir, "chat_message_mapping.json"
        )
        # 打开文件进行写入，使用UTF-8编码以支持中文
        with open(chat_mapping_file, "w", encoding="utf-8") as f:
            # json.dump 将Python对象转换为JSON格式并写入文件
            # ensure_ascii=False 允许写入非ASCII字符（如中文）
            # indent=2 设置缩进为2个空格，使JSON文件更易读
            json.dump(self.chat_message_mapping, f, ensure_ascii=False, indent=2)

         # 2. 保存聊天模型信息
        # chat_model.json 存储了每个聊天使用的模型信息
        chat_model_file = os.path.join(self.data_cache_dir, "chat_model.json")
        with open(chat_model_file, "w", encoding="utf-8") as f:
            json.dump(self.dify_chat_model, f, ensure_ascii=False, indent=2)

        # 3. 保存文件列表信息
        # file_list.json 存储了上传文件的相关信息
        file_list_file = os.path.join(self.data_cache_dir, "file_list.json")
        with open(file_list_file, "w", encoding="utf-8") as f:
            json.dump(self.dify_file_list, f, ensure_ascii=False, indent=2)

    def load_state(self):
        """从文件加载Dify相关的状态变量"""
        try:
            # chat_message_mapping.json
            chat_mapping_file = os.path.join(
                self.data_cache_dir, "chat_message_mapping.json"
            )
            if os.path.exists(chat_mapping_file):
                with open(chat_mapping_file, "r", encoding="utf-8") as f:
                    self.chat_message_mapping = json.load(f)
            else:
                self.chat_message_mapping = {}

            # chat_model.json
            chat_model_file = os.path.join(self.data_cache_dir, "chat_model.json")
            if os.path.exists(chat_model_file):
                with open(chat_model_file, "r", encoding="utf-8") as f:
                    self.dify_chat_model = json.load(f)
            else:
                self.dify_chat_model = {}

            # file_list.json
            file_list_file = os.path.join(self.data_cache_dir, "file_list.json")
            if os.path.exists(file_list_file):
                with open(file_list_file, "r", encoding="utf-8") as f:
                    self.dify_file_list = json.load(f)
            else:
                self.dify_file_list = {}

        except Exception as e:
            print(f"加载Dify状态文件失败: {e}")
            # 加载失败时使用空字典
            self.chat_message_mapping = {}
            self.dify_chat_model = {}
            self.dify_file_list = {}

    def get_models(self):
        """
        获取DIFY的模型列表
        """
        return [
            {"id": self.valves.DIFY_MODLE_ID, "name": self.valves.DIFY_WORKFLOW},
        ]


    def upload_file(self, user_id: str, file_path: str, mime_type: str) -> str:
        """
        上传文件到DIFY服务器
        
        Args:
            user_id: 用户ID
            file_path: 文件路径
            mime_type: 文件MIME类型
            
        Returns:
            str: 上传成功后返回的文件ID
            
        Raises:
            FileNotFoundError: 文件不存在
            requests.exceptions.RequestException: API请求失败
            ValueError: 服务器响应格式无效
        """
        try:
            url = f"{self.valves.DIFY_BASE_URL}/files/upload"
            headers = {
                "Authorization": f"Bearer {self.valves.DIFY_KEY}",
            }

            file_name = os.path.basename(file_path)
            
            # 使用 with 语句确保文件正确关闭
            with open(file_path, "rb") as file:
                files = {
                    "file": (file_name, file, mime_type),
                    "user": (None, user_id),
                }
                response = requests.post(url, headers=headers, files=files, timeout=(5, 30))
                response.raise_for_status()  # 检查响应状态
                
                result = response.json()
                if "id" not in result:
                    raise ValueError(f"服务器响应格式无效: {result}")
                    
                return result["id"]
            
        except FileNotFoundError:
            logging.error(f"文件未找到: {file_path}")
            raise
        except requests.exceptions.RequestException as e:
            logging.error(f"上传文件失败: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"处理文件时发生错误: {str(e)}")
            raise

    def upload_images(self, image_data_base64: str, user_id: str) -> str:
        """
        上传 base64 编码的图片到 DIFY 服务器，返回图片路径
        支持类型: 'JPG', 'JPEG', 'PNG', 'GIF', 'WEBP', 'SVG'
        """
        try:
            # Remove the data URL scheme prefix if present
            if image_data_base64.startswith("data:"):
                # Extract the base64 data after the comma
                image_data_base64 = image_data_base64.split(",", 1)[1]

            # 解码 base64 图像数据
            image_data = base64.b64decode(image_data_base64)

            # Create and save temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
                tmp_file.write(image_data)
                temp_file_path = tmp_file.name
            try:
                file_id = self.upload_file(user_id, temp_file_path, "image/png")
            finally:
                os.remove(temp_file_path)
            return file_id
        except Exception as e:
            raise ValueError(f"Failed to process base64 image data: {str(e)}")
        


    def pipes(self) -> List[dict]:
        return self.get_models()
    


    def pipe(self, body: dict, __event_emitter__: dict, __user__: Optional[dict], __task__=None) -> Union[str, Generator, Iterator]:
        #主流程
        if DEBUG_MODE:
            print("-----------------------------------------------------------------")
            print("Debug - Pipi Function ")
            print(f"body:{body}")
            print(f"__task__:{__task__}")
            print("-----------------------------------------------------------------")
        # 获取模型名称
        model_name = body["model"][body["model"].find(".") + 1 :]
        # 处理特殊任务
        if __task__ is not None:
            if __task__ == "title_generation":
                return model_name
            elif __task__ == "tags_generation":
                return f'{{"tags":[{model_name}]}}'

        # 获取当前用户
        current_user = __user__["email"]

        # 处理系统消息和普通消息
        system_message, messages = pop_system_message(body["messages"])
        if DEBUG_MODE:
            print(f"system_message:{system_message}")
            print(f"messages:{messages}, {len(messages)}")

        # 从event_emitter获取chat_id和message_id
        cell_contents = get_closure_info(__event_emitter__)
        chat_id = cell_contents["chat_id"]
        message_id = cell_contents["message_id"]
        # 处理对话模型和上下文
        parent_message_id = None
        # 在pipe函数中修改对话历史的处理逻辑
        if len(messages) == 1:
            # 新对话逻辑保持不变
            self.dify_chat_model[chat_id] = model_name
            self.chat_message_mapping[chat_id] = {
                "dify_conversation_id": "",
                "messages": []
            }
            self.dify_file_list[chat_id] = {}
        else:
            # 检查是否存在历史记录
            if chat_id in self.chat_message_mapping:
                # 首先验证模型
                if chat_id in self.dify_chat_model:
                    if self.dify_chat_model[chat_id] != model_name:
                        raise ValueError(f"Cannot change model in an existing conversation. This conversation was started with {self.dify_chat_model[chat_id]}")
                else:
                    # 如果somehow没有记录模型（异常情况），记录当前模型
                    self.dify_chat_model[chat_id] = model_name
                    
                chat_history = self.chat_message_mapping[chat_id]["messages"]
                current_msg_index = len(messages) - 1  # 当前消息的索引
                
                # 如果不是第一条消息，获取前一条消息的dify_id作为parent
                if current_msg_index > 0 and len(chat_history) >= current_msg_index:
                    previous_msg = chat_history[current_msg_index - 1]
                    parent_message_id = list(previous_msg.values())[0]                
                    # 关键修改：截断当前位置之后的消息历史
                    self.chat_message_mapping[chat_id]["messages"] = chat_history[:current_msg_index]
        # 获取最后一条消息作为query
        message = messages[-1]
        query = ""
        file_list = []
        # Dify APIs设置可选接入参数model与system_message.
        inputs = {
            "model": model_name,
            "system_message": system_message.get("content", "") if system_message else ""  # 更安全的访问方式
        }
        # 处理消息内容
        if isinstance(message.get("content"), list):
            for item in message["content"]:
                if item["type"] == "text":
                    query += item["text"]
                if item["type"] == "image_url":
                    upload_file_id = self.upload_images(item["image_url"]["url"], current_user)
                    upload_file_dict = {
                        "type": "image",
                        "transfer_method": "local_file",
                        "url": "",
                        "upload_file_id": upload_file_id
                    }
                    print("-----------------4------------------")
                    file_list.append(upload_file_dict)
        else:
            query = message.get("content", "")

        # 处理文件上传，如需上传多个文件这里改为轮询     
        with open('data/dify/dify_file_data.json', 'r', encoding='utf-8') as f:
            file_info = json.load(f)
        if DEBUG_MODE:
            print(f"file_info:{file_info}")
        if file_info.get("flag", False) is True:
            file_info["flag"] = False
            with open('data/dify/dify_file_data.json', 'w', encoding='utf-8') as f:
                json.dump(file_info, f, ensure_ascii=False, indent=2)
            url = f"{self.valves.DIFY_BASE_URL}/files/upload"
            try:
                file_name = file_info['name']
                file_extension = get_file_extension(file_name).upper()
                # 根据DifyAPI文件扩展名确定文件类型
                file_type = "custom"  # 默认类型
                if file_extension in ['TXT', 'MD', 'MARKDOWN', 'PDF', 'HTML', 'XLSX', 'XLS','DOC','DOCX', 'CSV', 'EML', 'MSG', 'PPTX', 'PPT', 'XML', 'EPUB']:
                    file_type = "document"
                elif file_extension in ['JPG', 'JPEG', 'PNG', 'GIF', 'WEBP', 'SVG']:
                    file_type = "image"
                elif file_extension in ['MP3', 'M4A', 'WAV', 'WEBM', 'AMR']:
                    file_type = "audio"
                elif file_extension in ['MP4', 'MOV', 'MPEG', 'MPGA']:
                    file_type = "video"
                file_DYFI_FILE_ID = self._get_file_dify_server(file_info["user_id"],f"{file_info['id']}_{file_info['name']}",)
                #file_path_url=f"{file_info['id']}_{file_info['name']}"
                #file_DYFI_FILE_ID=self.upload_file(file_id,f"data/uploads/{file_path_url}",file_type)
                print(f"------------------file_DYFI_FILE_ID=:{file_DYFI_FILE_ID}")

                file_list.append({
                    "type": file_type,
                    "transfer_method": "local_file",
                    "upload_file_id": file_DYFI_FILE_ID["id"]
                })                
                print(f"成功添加文件: {file_name}, 类型: {file_type}")
            except Exception as e:
                print(f"处理文件 {file_name} 失败: {str(e)}")

        if DEBUG_MODE:
            print(f"file_list:{file_list}")
        
        #开始发送数据到Dify API

        #构建载荷
        payload = {
            "inputs": inputs,
            "parent_message_id": parent_message_id,
            "query": query,
            "response_mode": "streaming" if body.get("stream", False) else "blocking",
            "conversation_id": self.chat_message_mapping[chat_id].get("dify_conversation_id", ""),
            "user": current_user,
            "files": file_list,
        }

        # 设置请求头
        headers = {
            "Authorization": f"Bearer {self.valves.DIFY_KEY}",
            "content-type": "application/json",
        }

        url = f"{self.valves.DIFY_BASE_URL}/chat-messages"

        try:
            if body.get("stream", False):
                return self.stream_response(url, headers, payload, chat_id, message_id)
            else:
                return self.non_stream_response(url, headers, payload, chat_id, message_id)
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return f"Error: Request failed: {e}"
        except Exception as e:
            print(f"Error in pipe method: {e}")
            return f"Error: {e}"


    def stream_response(self, url, headers, payload, chat_id, message_id):
        """处理流式响应"""
        try:
            with requests.post(url, headers=headers, json=payload, stream=True, timeout=(3.05, 60)) as response:
                if response.status_code != 200:
                    raise Exception(f"HTTP Error {response.status_code}: {response.text}")

                for line in response.iter_lines():
                    if line:
                        line = line.decode("utf-8")
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                event = data.get("event")
                                
                                if event == "message":
                                    # 处理普通文本消息
                                    yield data.get("answer", "")
                                elif event == "message_file":
                                    # 处理文件（图片）消息
                                    pass
                                elif event == "message_end":
                                    # 保存会话和消息ID映射
                                    dify_conversation_id = data.get("conversation_id", "")
                                    dify_message_id = data.get("message_id", "")
                                    
                                    self.chat_message_mapping[chat_id]["dify_conversation_id"] = dify_conversation_id
                                    self.chat_message_mapping[chat_id]["messages"].append({message_id: dify_message_id})
                                    
                                    # 保存状态
                                    self.save_state()
                                    break
                                elif event == "error":
                                    # 处理错误
                                    error_msg = f"Error {data.get('status')}: {data.get('message')} ({data.get('code')})"
                                    yield f"Error: {error_msg}"
                                    break

                                time.sleep(0.01)
                            except json.JSONDecodeError:
                                print(f"Failed to parse JSON: {line}")
                            except KeyError as e:
                                print(f"Unexpected data structure: {e}")
                                print(f"Full data: {data}")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            yield f"Error: Request failed: {e}"
        except Exception as e:
            print(f"General error in stream_response method: {e}")
            yield f"Error: {e}"

    def non_stream_response(self, url, headers, payload, chat_id, message_id):
        """处理非流式响应"""
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=(3.05, 60))
            if response.status_code != 200:
                raise Exception(f"HTTP Error {response.status_code}: {response.text}")

            res = response.json()
            
            # 保存会话和消息ID映射
            dify_conversation_id = res.get("conversation_id", "")
            dify_message_id = res.get("message_id", "")
            
            self.chat_message_mapping[chat_id]["dify_conversation_id"] = dify_conversation_id
            self.chat_message_mapping[chat_id]["messages"].append({message_id: dify_message_id})
            
            # 保存状态
            self.save_state()
            
            return res.get("answer", "")
        except requests.exceptions.RequestException as e:
            print(f"Failed non-stream request: {e}")
            return f"Error: {e}"

    def _get_file_dify_server(self, User_id: str, file_name: str) -> str:   
        #从本地uploads目录读取文件并以multipart/form-data格式上传到DIFY服务器       
        try:
            # 构建本地文件路径
            local_file_path = os.path.join('data/uploads', file_name)
            if DEBUG_MODE:
                print(f"读取本地文件: {local_file_path}")
            
            upload_url = self.valves.FILE_SERVER
            headers = {
                "Authorization": f"Bearer {self.valves.DIFY_KEY}"
            }
            
            # 准备文件数据和用户ID
            with open(local_file_path, 'rb') as file:
                files = {
                    'file': (file_name, file, 'application/octet-stream')
                }
                data = {
                    'user': User_id  # 添加用户ID参数
                }
                
                # 发送POST请求
                response = requests.post(
                    upload_url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=(5, 30)  # 连接超时5秒，读取超时30秒
                )           
                # 检查响应
                try:
                    response.raise_for_status()
                except requests.exceptions.HTTPError as e:
                    error_msg = f"HTTP错误: {e.response.status_code}"
                    if response.headers.get('content-type') == 'application/json':
                        error_detail = response.json()
                        error_msg += f" - {error_detail.get('message', '')}"
                    logging.error(error_msg)
                    raise
                
                result = response.json()
                required_fields = ['id', 'name']
                if not all(field in result for field in required_fields):
                    raise ValueError(f"服务器响应格式无效: {result}")
                if DEBUG_MODE:
                    print(f"文件上传成功: {result}")
                return result
                
        except FileNotFoundError:
            logging.error(f"文件未找到: {local_file_path}")
            raise
        except requests.exceptions.RequestException as e:
            logging.error(f"上传文件失败: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"处理文件失败: {str(e)}")
            raise           
  
