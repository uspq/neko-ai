import openai

openai.api_key = "your-api-key"
openai.base_url = "http://localhost:9999/v1/"

response = openai.chat.completions.create(
    model="neko-model",
    messages=[
        {"role": "system", "content": "你是一个有用的助手。"},
        {"role": "user", "content": "hi"}
    ],
    temperature=0.7
)
print(response.choices[0].message.content)