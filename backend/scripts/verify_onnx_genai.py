"""Verification script for onnxruntime-genai loading Qwen2.5-1.5B-Instruct."""

import sys
from pathlib import Path

import onnxruntime_genai as og


def main():
    model_dir = Path(__file__).resolve().parents[1] / "models" / "qwen2.5-1.5b-onnx"
    print(f"Checking model directory: {model_dir}")

    try:
        print("Attempting to load model from:", model_dir)
        model = og.Model(str(model_dir))
        tokenizer = og.Tokenizer(model)
        print("Successfully loaded model and tokenizer!")

        prompt = "<|im_start|>user\nSay hello!<|im_end|>\n<|im_start|>assistant\n"
        tokens = tokenizer.encode(prompt)
        print("Encoded tokens count:", len(tokens))

        params = og.GeneratorParams(model)
        params.set_search_options(max_length=64, temperature=0.2)

        generator = og.Generator(model, params)
        generator.append_tokens(tokens)
        tokenizer_stream = tokenizer.create_stream()

        print("Generating response: ", end="", flush=True)
        while not generator.is_done():
            generator.generate_next_token()
            new_token = generator.get_next_tokens()[0]
            chunk = tokenizer_stream.decode(new_token)
            print(chunk, end="", flush=True)
        print("\n\nVerification PASSED!")
    except Exception as e:
        print(f"Loading error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
