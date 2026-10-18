"""TTS quality verification with multiple voices and IoT texts."""
import asyncio
import httpx
import os

BASE = "http://localhost:8090"


async def main():
    tests = [
        ("IoT播报-女声", "zh-CN-XiaoxiaoNeural",
         "注意，3号水田堰板闸已开启，当前流量为每秒2.5立方米。"),
        ("IoT播报-男声", "zh-CN-YunyangNeural",
         "系统检测到离心泵运行异常，请前往现场检查。"),
        ("短文本", "zh-CN-XiaoxiaoNeural", "你好"),
        ("长文本", "zh-CN-YunxiNeural",
         "智慧农业物联网平台为您提供全方位的农田灌溉管理服务，"
         "包括水田堰板闸远程控制、渠田闸自动化调节、离心泵状态监控等功能。"),
        ("语速调节", "zh-CN-XiaoxiaoNeural",
         "设备标定已完成，即将进入运行模式。", "+20%"),
        ("音调调节", "zh-CN-XiaoyiNeural",
         "预警：水位超过警戒线，请立即处理。", None, "+5Hz"),
    ]

    results = []
    async with httpx.AsyncClient(timeout=30) as client:
        for item in tests:
            name = item[0]
            voice = item[1]
            text = item[2]
            rate = item[3] if len(item) > 3 else None
            pitch = item[4] if len(item) > 4 else None

            params = {"text": text, "voice": voice}
            if rate:
                params["rate"] = rate
            if pitch:
                params["pitch"] = pitch

            r = await client.post(f"{BASE}/tts", params=params)
            size = len(r.content)
            engine = r.headers.get("X-TTS-Engine", "?")
            ctype = r.headers.get("content-type", "?")

            safe_name = name.replace("-", "_").replace(" ", "_")
            fpath = f"tests/audio_{safe_name}.mp3"
            with open(fpath, "wb") as f:
                f.write(r.content)

            hdr = r.content[:2].hex()
            is_mp3 = (
                r.content[:2] == b"\xff\xfb"
                or r.content[:2] == b"\xff\xf3"
                or r.content[:3] == b"ID3"
            )

            status = "PASS" if r.status_code == 200 and size > 100 else "FAIL"
            extra = ""
            if rate:
                extra = f" rate={rate}"
            if pitch:
                extra = f" pitch={pitch}"

            results.append({
                "name": name + extra,
                "voice": voice,
                "status": status,
                "size_kb": size / 1024,
                "engine": engine,
                "format": "MP3" if is_mp3 else f"Unknown({hdr})",
                "file": fpath,
                "file_size": os.path.getsize(fpath),
            })

    # Print results table
    print()
    header = "{:<22} {:<28} {:<8} {:<10} {:<12} {:<8}".format(
        "Test", "Voice", "Status", "Size", "Engine", "Format"
    )
    print(header)
    print("-" * 92)
    for r in results:
        row = "{:<22} {:<28} {:<8} {:<10.1f} {:<12} {:<8}".format(
            r["name"], r["voice"], r["status"],
            r["size_kb"], r["engine"], r["format"]
        )
        print(row)
    print()

    # Verify saved files
    print("Saved audio files:")
    for r in results:
        ok = r["file_size"] > 100
        print(f"  {r['file']}: {r['file_size']} bytes ({'OK' if ok else 'FAIL'})")

    # Summary
    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    print(f"\nResult: {passed}/{total} tests passed")


if __name__ == "__main__":
    asyncio.run(main())
