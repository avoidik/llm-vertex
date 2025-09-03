import os
from typing import Optional
import llm
from google import genai
from google.genai import types


@llm.hookimpl
def register_models(register):
    # Source: https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models
    models = [
        'gemini-2.5-flash',
        'gemini-2.5-pro',
        'gemini-2.0-flash-lite',
        'gemini-2.0-flash',
        'gemini-1.5-pro',
        'gemini-1.5-flash',
    ]

    for model in models:
        register(Vertex(f'vertex-{model}'))

    # TODO: How to register custom models?


class Vertex(llm.Model):
    model_id = ""
    model_name = ""
    can_stream = True

    class Options(llm.Options):
        max_output_tokens: Optional[int] = None
        temperature: Optional[float] = None
        top_p: Optional[float] = None
        top_k: Optional[int] = None

    def __init__(self, model_id):
        self.model_id = model_id
        self.model_name = model_id.replace('vertex-', '')

        # TODO: Can we save these with llm keys set or something instead?
        project_id = os.getenv('VERTEX_PROJECT_ID')
        location = os.getenv('VERTEX_LOCATION', 'us-central1')

        self.client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location
        )

    def execute(self, prompt, stream, response, conversation):
        config = self.build_generation_config(prompt.options)
        if prompt.system:
            config.system_instruction = prompt.system

        if conversation:
            # Use chat session for conversations
            chat = self.client.chats.create(model=self.model_name)
            # Add conversation history
            history = self.build_history(conversation)
            for content in history:
                if content.get('role') == 'user':
                    chat.send_message(content.get('text', ''))

            if stream:
                responses = chat.send_message_stream(prompt.prompt, config=config)
                for chunk in responses:
                    yield chunk.text
            else:
                response_obj = chat.send_message(prompt.prompt, config=config)
                yield response_obj.text
        else:
            # Direct content generation
            if stream:
                responses = self.client.models.generate_content_stream(
                    model=self.model_name,
                    contents=prompt.prompt,
                    config=config
                )
                for chunk in responses:
                    yield chunk.text
            else:
                response_obj = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt.prompt,
                    config=config
                )
                yield response_obj.text

    def build_history(self, conversation):
        if not conversation:
            return []
        messages = []
        print(f"Build_history conversation: {conversation}")
        for response in conversation.responses:
            user_content = {"role": "user", "text": response.prompt.prompt}
            model_content = {"role": "model", "text": response.text()}
            messages.extend([user_content, model_content])
        return messages

    def build_generation_config(self, options):
        config_dict = options.model_dump()
        # Filter out None values
        config_dict = {k: v for k, v in config_dict.items() if v is not None}
        return types.GenerateContentConfig(**config_dict)
