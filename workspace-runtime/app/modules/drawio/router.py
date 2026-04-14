"""
Draw.io 整合路由
提供 Draw.io 圖表檢視和編輯的 API 端點
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import JSONResponse
import urllib.parse
import logging

from app.modules.file_system.service import FileService
from app.modules.file_system.dependencies import get_file_service_sync
from app.services.i18n_service import I18nService, get_i18n_service
from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/drawio", tags=["Draw.io 整合"])


@router.get("/viewer")
async def get_drawio_viewer_url(
    file_path: str = Query(..., description="檔案路徑"),
    mode: str = Query("view", description="模式: view 或 edit"),
    file_service: FileService = Depends(get_file_service_sync),
    translate: I18nService = Depends(get_i18n_service)
):
    """
    生成 Draw.io 檢視器 URL

    Args:
        file_path: 要檢視的 .drawio 檔案路徑
        mode: 檢視模式 (view/edit)

    Returns:
        包含 Draw.io URL 的 JSON 響應

    Raises:
        HTTPException: 當檔案不存在或讀取失敗時
    """
    try:
        logger.info(f"Generating Draw.io URL for file: {file_path}, mode: {mode}")

        # 讀取檔案內容
        file_response = file_service.read_file(file_path)
        content = file_response.content
        
        if not content or not content.strip():
            raise HTTPException(
                status_code=400,
                detail=translate("drawio.errors.empty_file")
            )
        
        # Draw.io 服務的外部 URL (瀏覽器可訪問)
        drawio_base_url = settings.DRAWIO_EXTERNAL_URL

        # 構建 URL 參數
        params = {
            "embed": "1",           # 啟用嵌入模式
            "proto": "json",        # 使用 JSON 協議進行 PostMessage 通訊
            "spin": "1",            # 顯示載入動畫
            "ui": "atlas",          # 使用 Atlas UI 主題
            "lang": "zh",           # 語言設定
        }

        # 根據模式設定不同的參數
        if mode == "edit":
            params.update({
                "modified": "unsavedChanges",  # 標記為未保存
                "saveAndExit": "1",            # 啟用保存並退出
                "noSaveBtn": "0",              # 顯示保存按鈕
            })
        else:
            # 檢視模式
            params.update({
                "chrome": "0",      # 隱藏工具列
                "nav": "1",         # 顯示導航控制
                "edit": "_blank",   # 編輯時在新視窗開啟
                "layers": "1",      # 顯示圖層
                "lightbox": "1",    # 啟用燈箱模式
            })

        # 構建完整 URL
        query_string = urllib.parse.urlencode(params)
        # 不在 URL 中嵌入 XML，而是通過 PostMessage 發送
        # 前端會在收到 init 事件後發送 load 消息
        full_url = f"{drawio_base_url}/?{query_string}"
        
        logger.info(f"Generated Draw.io URL successfully for {file_path}")
        
        return JSONResponse(content={
            "url": full_url,
            "mode": mode,
            "file_path": file_path
        })
        
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        raise HTTPException(
            status_code=404,
            detail=translate("drawio.errors.file_not_found", file_path=file_path)
        )
    except Exception as e:
        logger.error(f"Error generating Draw.io URL: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=translate("drawio.errors.url_generation_failed", error=str(e))
        )


@router.post("/save")
async def save_drawio_file(
    file_path: str = Query(..., description="檔案路徑"),
    content: str = Body(..., description="XML 內容", embed=True),
    file_service: FileService = Depends(get_file_service_sync),
    translate: I18nService = Depends(get_i18n_service)
):
    """
    保存 Draw.io 檔案

    Args:
        file_path: 檔案路徑
        content: XML 內容

    Returns:
        保存結果的 JSON 響應

    Raises:
        HTTPException: 當保存失敗時
    """
    try:
        logger.info(f"Saving Draw.io file: {file_path}")

        # 驗證內容不為空
        if not content or not content.strip():
            raise HTTPException(
                status_code=400,
                detail=translate("drawio.errors.empty_content")
            )

        # 驗證是否為有效的 XML
        # 簡單檢查：確保包含 mxfile 或 mxGraphModel 標籤
        if not ("<mxfile" in content or "<mxGraphModel" in content):
            logger.warning(f"Invalid Draw.io XML format for {file_path}")
            raise HTTPException(
                status_code=400,
                detail=translate("drawio.errors.invalid_xml")
            )

        # 保存檔案
        file_service.write_file(file_path, content)
        
        logger.info(f"Draw.io file saved successfully: {file_path}")
        
        return JSONResponse(content={
            "success": True,
            "message": translate("drawio.save_success"),
            "file_path": file_path
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving Draw.io file: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=translate("drawio.errors.save_failed", error=str(e))
        )

