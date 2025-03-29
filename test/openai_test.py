from openai import OpenAI

# 初始化客户端
client = OpenAI(
    api_key="your-api-key",  # 可以是任意字符串，因为我们的服务不验证
    base_url="http://localhost:9999/v1"  # 指定我们的服务地址
)

# 发送请求
response = client.chat.completions.create(
    model="neko-ai",
    messages=[
        {
            "role": "user",
            "content": "你好",
            "name": "string"
        }
    ],
    temperature=0.7,
    top_p=1,
    n=1,
    max_tokens=2000,
    stop=["string"],
    presence_penalty=0,
    frequency_penalty=0,
    user="string",
    stream=False,
    # Neko-AI 特有参数，需要通过 extra_body 传递
    extra_body={
        "use_memory": True,
        "use_knowledge": False,
        "use_web_search": False
    }
)

# 打印响应
print(response.choices[0].message.content)