"""
title: DIFY Filter
authors: Estel
author_url: https://github.com/estel_li
funding_url: https://github.com/open-webui
version: 0.1
description: 该流程用于DIFY的API接口，对openweb-ui用户上传的文件进行预处理。
"""
from pydantic import BaseModel, Field
from typing import Optional
import json

DEBUG_MODE = True

class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=0, description="Priority level for the filter operations."
        )
        max_turns: int = Field(
            default=8, description="Maximum allowable conversation turns for a user."
        )
        pass

    class UserValves(BaseModel):
        pass

    def __init__(self):
        #文件处理标识
        #self.file_handler = True 
        self.valves = self.Valves()
        pass
    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:

        if DEBUG_MODE:
            print(f"inlet:{__name__}")
            print(f"inlet:body:{body}")
            print(f"inlet:user:{__user__}")        
        if body.get('model') != "difyapitest.dify_id":
            return body
        try:
            with open('data/dify/dify_file_data.json', 'r', encoding='utf-8') as f:
                dify_file = json.load(f)
                if not dify_file:
                    return body
        except Exception as e:
            print(f"读取文件时出错或文件为空: {str(e)}")
        if "files" not in body:
            return body
        
        #因上传的数据openwebui已经向量化
        #曲线救国传递文件信息，可以修改用其他方法   
        #实际目前上传文档Dify API只需要文件id和用户两个值即可 
        for file_info in body['files']:    
            if file_info['type'] != 'file':
                continue
            print(f"file_info:{file_info}")
            # 检查文件大小（15MB = 15 * 1024 * 1024 bytes）
            MAX_FILE_SIZE = 15 * 1024 * 1024
            file_size = file_info.get('size', 0) 
            print(f"file_size:{file_size}")
            if file_size > MAX_FILE_SIZE:
                print(f"跳过大文件: {file_info['name']}, 大小: {file_size/1024/1024:.2f}MB")
                continue
            dify_file = {
                "content": file_info['file']['data']['content'],  
                "name": file_info['name'],
                "id": file_info['id'],
                "user_id": file_info['file']['user_id'],
                "content_type": file_info["file"]['meta']['content_type'],
                "size": file_info['file']['meta']['size'],
                "collection_name": file_info['collection_name'],
                "url": file_info['url'],
                "flag":True,
            }
            try:
                with open('data/dify/dify_file_data.json', 'w', encoding='utf-8') as f:
                    json.dump(dify_file, f, ensure_ascii=False)
            except Exception as e:
                print(f"写入文件时出错: {str(e)}")
        return body

    def outlet(self, body: dict, user: Optional[dict] = None) -> dict:
        # Modify or analyze the response body after processing by the API.
        # This function is the post-processor for the API, which can be used to modify the response
        # or perform additional checks and analytics.
        if DEBUG_MODE:
            print(f"outlet:{__name__}")
            print(f"outlet:body:{body}")
            print(f"outlet:user:{user}")
        return body
