"""Motor Text-to-SQL basado en un modelo de Hugging Face (T5 afinado en WikiSQL)."""
from transformers import T5ForConditionalGeneration, T5Tokenizer

MODEL_NAME = "mrm8488/t5-base-finetuned-wikiSQL"


class TextToSQL:
    def __init__(self, model_name: str = MODEL_NAME):
        self.tokenizer = T5Tokenizer.from_pretrained(model_name)
        self.model = T5ForConditionalGeneration.from_pretrained(model_name)

    def generate(self, question: str) -> str:
        prompt = f"translate English to SQL: {question} </s>"
        features = self.tokenizer([prompt], return_tensors="pt")
        output_ids = self.model.generate(
            input_ids=features["input_ids"],
            attention_mask=features["attention_mask"],
            max_length=128,
        )
        return self.tokenizer.decode(output_ids[0], skip_special_tokens=True)
