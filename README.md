# openweb-ui_to_dify  

用于连接 openweb-ui 和 Dify API 的工具。它允许用户通过 openweb-ui 发送文本、图像或文档到 Dify 的对话流和工作流中。该工具通过在 openweb-ui 中集成脚本来选择合适的模型，从而实现与 Dify API 的交互。
修改环境变量后，在函数中加入*dify_pipe.py*和*dify_Filter.py*,并开启函数和过滤功能。 
dify_Workflow函数可以对接dify,使用dify的工作流。我上传了一个dify的工作流示例以供参考。
flux_schnell.dsl是一个dify的工作流，调用了本地Comfy-UI API,使用*Flux_1_schnell*模型来快速生成图片。

A tool for connecting openweb-ui with the Dify API. It allows users to send text, images, or documents from openweb-ui to Dify's conversation and workflow streams. This tool integrates scripts within openweb-ui to select the appropriate model, enabling interaction with the Dify API.

After modifying the environment variables, include *dify_pipe.py* and *dify_Filter.py* in the function, and enable the function and filtering features. The dify_Workflow function can interface with Dify, utilizing Dify's workflows. I have uploaded a sample Dify workflow for reference.

flux_schnell.dsl is a Dify workflow that calls the local Comfy-UI API, using the *Flux_1_schnell* model to quickly generate images.





