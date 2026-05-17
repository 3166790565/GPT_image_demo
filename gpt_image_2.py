import os
import sys
import argparse
import base64
from pathlib import Path

from openai import OpenAI


OUTPUT_DIR = Path(__file__).parent / "output"


def parse_args():
    parser = argparse.ArgumentParser(description="调用 OpenAI GPT-Image-2 生成图像")
    parser.add_argument("prompt", nargs="?", help="图像描述提示词（如不提供则使用默认提示词）")
    parser.add_argument("-m", "--model", default="gpt-image-2", help="模型名称，默认 gpt-image-2")
    parser.add_argument("-s", "--size", default="1024x1024",
                        choices=["1024x1024", "1024x1536", "1536x1024",
                                 "2000x1000", "1000x2000", "2000x667", "667x2000"],
                        help="图像尺寸，默认 1024x1024")
    parser.add_argument("-q", "--quality", default="high", choices=["standard", "high"],
                        help="图像质量，默认 high")
    parser.add_argument("-n", "--count", type=int, default=1, choices=range(1, 11),
                        metavar="[1-10]", help="生成图像数量 (1-10)，默认 1")
    parser.add_argument("-t", "--thinking", default=None,
                        choices=["off", "low", "medium", "high"],
                        help="推理模式，不指定则使用模型默认值")
    parser.add_argument("-f", "--format", dest="response_format", default="b64_json",
                        choices=["url", "b64_json"],
                        help="响应格式，默认 b64_json（直接保存为文件）")
    parser.add_argument("--bg", "--background", dest="background", default=None,
                        choices=["auto", "transparent", "opaque"],
                        help="背景模式")
    parser.add_argument("--seed", type=int, default=None,
                        help="随机种子 (int32)，用于结果复现（非精确）")
    parser.add_argument("--api-key", dest="api_key",
                        help="OpenAI API Key，默认读取环境变量 OPENAI_API_KEY")
    parser.add_argument("--base-url", dest="base_url",
                        help="自定义 API 基础地址（适用于中转代理）")
    parser.add_argument("-o", "--output", default=None,
                        help="输出目录，默认 ./output")
    parser.add_argument("--prefix", default="gpt-image",
                        help="输出文件名前缀，默认 gpt-image")
    return parser.parse_args()


def save_image_from_url(url: str, save_path: Path):
    import requests
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    save_path.write_bytes(resp.content)


def save_image_from_b64(b64_str: str, save_path: Path):
    image_bytes = base64.b64decode(b64_str)
    save_path.write_bytes(image_bytes)


def main():
    args = parse_args()

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("错误：未提供 API Key。请通过 --api-key 参数或设置 OPENAI_API_KEY 环境变量。")
        sys.exit(1)

    client_kwargs = {"api_key": api_key}
    if args.base_url:
        client_kwargs["base_url"] = args.base_url

    client = OpenAI(**client_kwargs)

    prompt = args.prompt or "一只橘猫坐在窗台上晒太阳，水彩画风格，温暖的午后光线，高细节"
    output_dir = Path(args.output) if args.output else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    params = {
        "model": args.model,
        "prompt": prompt,
        "n": args.count,
        "size": args.size,
        "quality": args.quality,
        "response_format": args.response_format,
    }
    if args.thinking is not None:
        params["thinking"] = args.thinking
    if args.background is not None:
        params["background"] = args.background
    if args.seed is not None:
        params["seed"] = args.seed

    print(f"正在请求 GPT-Image-2…")
    print(f"  模型: {params['model']}")
    print(f"  提示词: {params['prompt'][:80]}{'...' if len(params['prompt']) > 80 else ''}")
    print(f"  尺寸: {params['size']}  质量: {params['quality']}  数量: {params['n']}")
    if args.thinking:
        print(f"  推理模式: {args.thinking}")

    try:
        response = client.images.generate(**params)
    except Exception as e:
        print(f"API 请求失败: {e}")
        sys.exit(1)

    print(f"生成成功！共 {len(response.data)} 张图像\n")

    for i, image_data in enumerate(response.data):
        suffix = "png"
        filename = f"{args.prefix}_{i+1:02d}.{suffix}"
        save_path = output_dir / filename

        if args.response_format == "b64_json":
            save_image_from_b64(image_data.b64_json, save_path)
        else:
            revised_prompt = getattr(image_data, "revised_prompt", None)
            save_image_from_url(image_data.url, save_path)
            if revised_prompt:
                print(f"  [修订提示词]: {revised_prompt}")

        print(f"  [{i+1}/{len(response.data)}] 已保存: {save_path}")


if __name__ == "__main__":
    main()
