import sys
import os

# 将当前目录添加到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import uvicorn
from core.config import settings
from api.router import api_router
from utils.logger import logger, get_logger

# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境应该限制
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "Accept", "Origin"],
    expose_headers=["X-Process-Time"],
    max_age=600,  # 预检请求结果缓存10分钟
)

# 添加请求处理中间件
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    
    try:
        # 生成请求ID
        request_id = f"req_{int(time.time())}"
        
        # 记录基本请求信息，不读取请求体
        api_logger.info(
            f"[{request_id}] 请求开始: {request.method} {request.url.path} "
            f"- 客户端: {request.client.host}"
        )
        
        # 处理响应
        response = await call_next(request)
        
        # 记录响应信息
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        api_logger.info(
            f"[{request_id}] 响应: {request.method} {request.url.path} "
            f"- 状态码: {response.status_code} "
            f"- 处理时间: {process_time:.4f}s"
        )
        
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        api_logger.error(
            f"{request.method} {request.url.path} "
            f"- Error: {str(e)} "
            f"- Process Time: {process_time:.4f}s"
        )
        
        return JSONResponse(
            status_code=500,
            content={"detail": f"内部服务器错误: {str(e)}"}
        )

# 注册API路由
app.include_router(api_router, prefix="/api")

# 直接注册 v1 路由以兼容 OpenAI API 格式
from api.routes import v1
app.include_router(v1.router)

# 根路由
@app.get("/")
async def root():
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": settings.APP_DESCRIPTION,
        "docs_url": "/docs",
        "api_prefix": "/api"
    }

# 直接运行时的入口
def start():
    # 确保必要的目录存在
    os.makedirs(settings.LOGS_DIR, exist_ok=True)
    os.makedirs(settings.BACKUPS_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(settings.FAISS_INDEX_PATH), exist_ok=True)
    os.makedirs(settings.KNOWLEDGE_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(settings.KNOWLEDGE_INDEX_PATH), exist_ok=True)
    
    # 检查是否需要初始化数据库
    # 如果是直接运行main.py，则需要初始化数据库
    # 如果是通过run.py运行，则已经初始化过数据库
    if os.path.basename(sys.argv[0]) == 'main.py':
        from utils.db_init import init_all_databases
        logger.info("开始初始化数据库...")
        try:
            init_result = init_all_databases()
            if not init_result:
                logger.warning("数据库初始化未完全成功，服务可能无法正常工作")
            else:
                logger.info("数据库初始化成功")
        except Exception as e:
            logger.error(f"数据库初始化失败: {str(e)}", exc_info=True)
            logger.warning("数据库初始化失败，但仍尝试启动服务")
    else:
        logger.info("跳过数据库初始化，假设已通过run.py完成初始化")
    
    # 启动服务
    logger.info(f"启动 {settings.APP_NAME} 服务")
    uvicorn.run(
        "main:app",
        host="localhost",
        port=9999,
        reload=settings.DEBUG
    )

# 然后在文件中添加
api_logger = get_logger("api")

if __name__ == "__main__":
    start() 