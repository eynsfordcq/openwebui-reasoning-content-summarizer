"""
title: Reasoning Content Summarizer
author: eynsfordcq
github_url: https://github.com/eynsfordcq/openwebui-reasoning-content-summarizer
version: 0.1
"""

import requests
from pydantic import BaseModel, Field

class Filter:
    class Valves(BaseModel):
        content_tag: str = Field(
            default="content",
            description="The content tag of the api response. Defaults to 'content'.",
        )
        reasoning_tag: str = Field(
            default="reasoning",
            description="The reasoning tag of the api response. Defaults to 'reasoning', some provider uses 'reasoning_content'.",
        )
        api_url: str = Field(
            default="https://api.groq.com/openai/v1/chat/completions",
            description="The API URL for the summarization LLM.",
        )
        api_token: str = Field(
            default=None,
            description="The API token for authentication."
        )
        model: str = Field(
            default="llama-3.1-8b-instant",
            description="The model to be used for summarization.",
        )
        threshold: int = Field(
            default=350,
            description="Token count to accumulate before sending to LLM for summarization."
        )

    def __init__(self):
        self.valves = self.Valves()
        self.thinking_open = False
        self.buffer = []
        self.token_count = 0

    def _summarize_text(self) -> str:
        _content = "".join(self.buffer)
        print(_content)
        payload = {
            "model": self.valves.model,
            "messages": [{
                "role": "user", 
                "content": f"""
                **Task:**  
                - Summarize the internal thoughts of "me" in **one to two sentences**, keep it **short and concise**.
                - **Do not** reveal that these are internal thoughts.  
                - If the thoughts are incomplete, **make a best-effort summary**.  
                - **Generate a concise and relevant title** for the summary.  
                - Format the title in **bold**.  

                **Example Output:**  
                ```  
                **Comparing Two Numbers**  
                The user needs to compare two digits. I need to break down the steps logically.  
                ```  

                **Input:**  
                
                <thoughts>  
                {_content}  
                </thoughts>
                """
            }],
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.valves.api_token}",
        }

        try:
            response = requests.post(self.valves.api_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            self.content_buffer = ""
            self.token_count = 0
            summary = data["choices"][0]["message"]["content"].strip() + "\n\n"
        except Exception as e:
            print(f"summarize went wrong: {e}")
            summary = _content
        finally:
            self.token_count = 0
            self.content_buffer = []
            return summary

    def stream(self, event: dict) -> dict:
        reasoning_tag = self.valves.reasoning_tag
        content_tag = self.valves.content_tag
        
        if not event.get("choices"):
            return event
        
        delta = event["choices"][0].get("delta", {})
        if not delta.get(content_tag) and delta.get(reasoning_tag):
            reasoning_text = delta[reasoning_tag]
            self.buffer.append(reasoning_text)
            self.token_count += 1

            if self.token_count >= self.valves.threshold:
                summary = self._summarize_text()
                if not self.thinking_open:
                    delta[content_tag] = f"<thinking>{summary}"
                    self.thinking_open = True
                else:
                    delta[content_tag] = summary
            
            # clear the reasoning field.
            delta[self.valves.reasoning_tag] = ""

        elif delta.get(content_tag) and self.thinking_open:
            # if there are still stuff in the buffer
            summary = ""
            if self.buffer:
                summary = self._summarize_text()
            
            delta[content_tag] = (
                f"{summary}</thinking>\n{delta[content_tag]}"
            )
            self.thinking_open = False

        return event
