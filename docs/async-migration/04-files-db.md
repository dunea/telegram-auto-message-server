# PR #4 · 阶段 4：files DB 部分

## 目标

迁移 file 子系统到 async。S3 部分保留同步 boto3，用 `asyncio.to_thread` 桥接避免阻塞 event loop。

## 改动文件清单

| 文件 | 类型 | 改动点 |
|------|------|--------|
| `app/repository/file_repository.py` | 修改 | 14 个方法改 async；构造函数 `session: AsyncSession` |
| `app/service/file_service.py` | 修改 | 11 个方法改 `async def`；boto3 调用全部包 `await asyncio.to_thread(...)`；`UploadFile`/`DownloadFile`/`DeleteFile` 内部以线程池跑 boto3 |
| `app/api/routes/files.py` | 修改 | 5 个路由改 `async def`；Depends 改 `get_async_db_session` |
| `app/web/routes/files.py` | 修改 | 4 个路由改 `async def`；Depends 改 `get_async_db_session` |
| `app/api/deps.py` | 修改 | 新增 `get_async_file_service` 工厂（与 `get_file_service` 并存） |

## 关键代码骨架

### `app/service/file_service.py` boto3 桥接

```python
import asyncio
import boto3


class FileService:
    async def UploadFile(self, file_obj, file_name: str, content_type: str):
        record = FileRecord(name=file_name, content_type=content_type, ...)
        await self._file_record_repository.Save(record)
        await asyncio.to_thread(
            self._s3_client.upload_fileobj,
            file_obj,
            self._settings.s3_bucket_name,
            record.object_key,
        )
        await self._session.commit()
        return record

    async def DownloadFile(self, file_id: int) -> bytes:
        record = await self._file_record_repository.FindById(file_id)
        if record is None:
            return None
        buffer = io.BytesIO()
        await asyncio.to_thread(
            self._s3_client.download_fileobj,
            self._settings.s3_bucket_name,
            record.object_key,
            buffer,
        )
        buffer.seek(0)
        return buffer.getvalue()

    async def SoftDeleteFile(self, file_id: int) -> None:
        record = await self._file_record_repository.FindById(file_id)
        if record is None:
            return
        record.deleted_at = datetime.utcnow()
        await self._session.commit()
        await asyncio.to_thread(
            self._s3_client.delete_object,
            Bucket=self._settings.s3_bucket_name,
            Key=record.object_key,
        )
```

## 风险点

1. **boto3 client 是线程安全的**（boto3 官方保证），`asyncio.to_thread` 跨线程共享 OK。
2. **大文件下载**：`buffer` 在内存中累积可能 OOM；`to_thread` 不解决流式问题，**但与现有 sync 行为一致**，PR #10 改 aioboto3 时再优化。
3. **`file_obj` 是 `UploadFile` 句柄**，跨线程访问是否安全？FastAPI 的 `UploadFile` 底层是 `SpooledTemporaryFile`，**线程安全**。OK。

## 验证步骤

```bash
python -m pytest -q --ignore=tests/e2e
python -m pytest -q tests/test_web_messages_files.py -v
# 手动 smoke
curl -X POST http://127.0.0.1:8001/api/v1/files -F 'file=@README.md'
curl -X GET http://127.0.0.1:8001/api/v1/files/<id>/download -o /tmp/out
curl -X DELETE http://127.0.0.1:8001/api/v1/files/<id>
```

## 回滚方案

`git revert <commit-sha-of-PR#4>`

## 完成判据

- [ ] `file_repository.py` 14 个方法 async
- [ ] `file_service.py` 11 个方法 async
- [ ] boto3 调用全部 `await asyncio.to_thread(...)` 包装
- [ ] 5 个 API 路由 + 4 个 web 路由 async
- [ ] `pytest -q` 全绿
- [ ] 手测上传/下载/删除/列表
