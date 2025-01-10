"""
title: DIFY Manifold Pipe
authors: Estel
author_url: https://github.com/estel_li
funding_url: https://github.com/xuzhougeng
funding_url: https://github.com/open-webui
version: 0.1
description: 该流程用于DIFY的API接口，用以对接Dify的工作流
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


class Pipe:
    class Valves(BaseModel):
        # 环境变量
        DIFY_BASE_URL: str = Field(default="http://192.168.1.5/v1")
        DIFY_KEY: str = Field(default="app-etbyck5NpmERpP9qA7UzG3Kx")
        FILE_SERVER: str = Field(default="http://192.168.1.5/v1/files/upload")
        DIFY_WORKFLOW: str = Field(default="Dify_Flux_schnell")
        DIFY_MODLE_ID: str = Field(default="dify_t2i")

    def __init__(self):
        self.type = "manifold"
        self.id = "dify_flux_schnell"
        self.name = "dify/"
        self.valves = self.Valves()
                


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
            print("Debug - Dify-Workflow Function")
            print("Flux-schnell")
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

        # 获取最后一条消息作为query
        message = messages[-1]
        query = ""
        file_list = []
        # Dify APIs设置可选接入参数model与system_message.

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
                    file_list.append(upload_file_dict)
        else:
            query = message.get("content", "")
        print(f"query:{query}")
        inputs = {
            "model": model_name,
            "prompt": query 
        }    
        print(f"inputs:{inputs}")
        #开始发送数据到Dify API
        #构建载荷
        payload = {
            "inputs": inputs,
            "response_mode": "streaming" if body.get("stream", False) else "blocking",
            "user": current_user,
            "files": file_list,
        }

        # 设置请求头
        headers = {
            "Authorization": f"Bearer {self.valves.DIFY_KEY}",
            "content-type": "application/json",
        }

        url = f"{self.valves.DIFY_BASE_URL}/workflows/run"

        try:
            if body.get("stream", False):
                return self.stream_response(url, headers, payload,)
            else:
                return self.non_stream_response(url, headers, payload)
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return f"Error: Request failed: {e}"
        except Exception as e:
            print(f"Error in pipe method: {e}")
            return f"Error: {e}"


    def stream_response(self, url, headers, payload):
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
                                
                                if event == "workflow_started":
                                    #yield f"Workflow started: {data.get('workflow_run_id')}"
                                    #yield "工作流已经启动 Workflow is running..... "
                                    pass
                                elif event == "node_started":
                                    # 处理节点开始事件
                                    #node_data = data.get("data", {})
                                    #yield f"Node started: {node_data.get('title')} ({node_data.get('node_type')})"
                                    pass
                                elif event == "node_finished":
                                    # 处理节点完成事件
                                    '''
                                    node_data = data.get("data", {})
                                    if node_data.get("status") == "succeeded":
                                        yield f"Node completed: {node_data.get('title')} ({node_data.get('node_type')})"
                                    else:
                                        yield f"Node failed: {node_data.get('title')} ({node_data.get('node_type')})"
                                    '''
                                elif event == "workflow_finished":
                                    # 处理工作流完成事件
                                    workflow_data = data.get("data", {})
                                    if workflow_data.get("status") == "succeeded":
                                        outputs = workflow_data.get('outputs', {})
                                        for value in outputs.values():
                                            if isinstance(value, list):
                                                for item in value:
                                                    if item.get("type","")=="image":
                                                        print(f"--------item:{item}")
                                                        yield self.handle_image_response(item)
                                                    else:
                                                        yield item
                                        break                                                                 
                                    else:
                                        yield f"Workflow failed: {workflow_data.get('error', 'Unknown error')}"
                                        break
                                elif event == "tts_message":
                                    # 处理TTS音频消息
                                    yield f"TTS audio received: {data.get('audio')[:50]}..."
                                elif event == "tts_message_end":
                                    # 处理TTS结束事件
                                    yield "TTS audio stream ended"
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

    def non_stream_response(
        self, URL,headers, payload
    ) -> str:
        """
        Get a non-streaming response from the API.

        Args:
            headers (Dict[str, str]): The headers for the request.
            payload (Dict[str, Any]): The payload for the request.

        Returns:
            str: The response from the API.
        """
        try:
            response = requests.post(
                url=URL,
                headers=headers,
                json=payload,
                stream=False,
                timeout=(3.05, 60),
            )
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return self.handle_json_response(response)
            elif "image/" in content_type:
                return self.handle_image_response(response)
            else:
                return f"Error: Unsupported content type {content_type}"

        except requests.exceptions.HTTPError as e:
            return f"HTTP Error: {e} - {response.text}"
        except requests.exceptions.RequestException as e:
            return f"Error: Request failed: {e}"
        except Exception as e:
            return f"Error: {e}"
    
    def handle_image_response(self, output_image) -> str:
        """
        处理API返回的图像响应

        Args:
            output_image (dict): 包含图像信息的字典

        Returns:
            str: 格式化后的图像数据，包含Markdown格式的图像链接和文件信息
        """
        try:
            img_data = output_image  # 取第一个图像
            img_url = img_data.get("url")
            img_ext = img_data.get("extension", ".png").strip(".")
            
            # 构建完整的图片URL
            # 优化后的URL处理逻辑
            base_url = self.valves.DIFY_BASE_URL.rstrip("/v1")  # 去掉末尾的 /v1
            img_url = img_url.lstrip("/")  # 移除开头的所有斜杠
            full_url = f"{base_url}/{img_url}"  # 自动处理斜杠
            # 返回Markdown格式的图像链接
            return f"![Image]({full_url})\n`GeneratedImage.{img_ext}`"
                
        except Exception as e:
            logging.error(f"处理图像响应时出错: {str(e)}")
            return f"Error: Failed to process image response - {str(e)}"