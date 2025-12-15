from pathlib import Path

from kimidake_bot.config import get_settings
from kimidake_bot.logic.fortune_generator import FortuneGenerator, FortuneInput
from kimidake_bot.services.openai_client import OpenAITextClient

def main():
    settings = get_settings()

    prompts_dir = Path(__file__).parent / "prompts"
    llm = OpenAITextClient(api_key=settings.openai_api_key)
    gen = FortuneGenerator(prompts_dir=prompts_dir, llm_client=llm)

    # 仮入力（ここをLINEの入力に置き換える）
    fi = FortuneInput(
        nickname="ak",
        birthday="2000/11/22",
        gender="男",
        concern="やりたいことはあるのに動けない",
    )

    text = gen.generate(fi, settings=settings)
    print("\n--- 君だけ ---\n")
    print(text)

if __name__ == "__main__":
    main()
