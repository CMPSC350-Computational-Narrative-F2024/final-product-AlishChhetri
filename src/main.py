import os
import requests
import json
from load_key import OPEN_AI_KEY, OPEN_AI_ORG
from openai import OpenAI
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Image, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# Initialize OpenAI client with API key and organization ID
client = OpenAI(api_key=OPEN_AI_KEY, organization=OPEN_AI_ORG)


def read_story_details(json_path):
    """
    Reads a JSON file containing details about the story, characters, and rules.
    """
    try:
        with open(json_path, "r") as file:
            story_details = json.load(file)

        if "Story" not in story_details or "Characters" not in story_details:
            raise ValueError("JSON must contain 'Story' and 'Characters' keys.")

        return {
            "Story": story_details.get("Story", {}),
            "Characters": story_details.get("Characters", []),
            "DungeonMasterNotes": story_details.get("DungeonMasterNotes", {}),
        }

    except FileNotFoundError:
        raise FileNotFoundError(f"The file at '{json_path}' was not found.")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")
    except Exception as e:
        raise Exception(f"An error occurred while reading the JSON: {e}")


def split_content(content, max_length=2000):
    """
    Splits content into smaller chunks to avoid exceeding token limits.
    """
    words = content.split()
    chunks = []
    current_chunk = []

    for word in words:
        current_chunk.append(word)
        if len(" ".join(current_chunk)) >= max_length:
            chunks.append(" ".join(current_chunk))
            current_chunk = []

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def format_to_paragraphs(text):
    """
    Splits text into paragraphs with tab indentation.
    """
    sentences = text.split(". ")
    paragraphs = []
    current_paragraph = []

    for sentence in sentences:
        current_paragraph.append(sentence.strip())
        if len(current_paragraph) >= 3:  # Approx. 3 sentences per paragraph
            paragraphs.append("\t" + " ".join(current_paragraph).strip() + ".")
            current_paragraph = []

    if current_paragraph:
        paragraphs.append("\t" + " ".join(current_paragraph).strip() + ".")

    return paragraphs


def generate_text(content, story_details):
    """
    Generates text for a chapter narrative based on the provided content and story details.
    """
    character_info = "\n".join(
        [
            f"{char['Name']} is known as {char['Character']}, described as {char['Appearance']} and plays the role of {char['Role']}."
            for char in story_details["Characters"]
        ]
    )
    plot = story_details["Story"].get("Plot", "")
    theme = story_details["DungeonMasterNotes"].get("Theme", "adventurous")

    chunks = split_content(content, max_length=2000)
    full_story = ""

    for chunk in chunks:
        print("Processing chunk...")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a skilled fantasy author. Write a cohesive, compelling, and linear story based around a DnD campign transcript."
                        f"based on the given input. Only use the characters' roleplay names and descriptions provided below. "
                        f"The story must follow the theme '{theme}' and include the plot '{plot}'. Format the story into clear, "
                        "distinct paragraphs with smooth transitions. Use descriptive language to engage the reader, ensuring proper grammar."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Characters:\n{character_info}\n\nStory Content:\n{chunk}",
                },
            ],
        )
        full_story += response.choices[0].message.content.strip() + "\n\n"

    paragraphs = format_to_paragraphs(full_story)
    return paragraphs


def generate_image(prompt, chapter_name, image_dir):
    """
    Generates or retrieves a cached image for a chapter based on the prompt.
    """
    os.makedirs(image_dir, exist_ok=True)
    image_filename = os.path.join(
        image_dir, f"{chapter_name.replace(' ', '_').lower()}_image.png"
    )

    if os.path.exists(image_filename):
        print(f"Using cached image for '{chapter_name}'.")
        return image_filename

    dalle_url = "https://api.openai.com/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {OPEN_AI_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "dall-e-3",
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
    }

    response = requests.post(dalle_url, headers=headers, json=data)

    if response.status_code == 200:
        image_url = response.json()["data"][0]["url"]
        with open(image_filename, "wb") as f:
            f.write(requests.get(image_url).content)
        print(f"Generated new image for '{chapter_name}'.")
        return image_filename
    else:
        raise Exception(
            f"Image generation failed: {response.status_code} {response.text}"
        )


def create_pdf(chapters, images, output_path):
    """
    Generates a PDF with text and images for each chapter, including additional images every 5 paragraphs.
    """
    styles = getSampleStyleSheet()
    centered_style = ParagraphStyle(name="Centered", alignment=1, fontSize=24)
    body_text_style = ParagraphStyle(name="BodyText", alignment=0, fontSize=12)

    pdf = SimpleDocTemplate(output_path, pagesize=letter)
    elements = []

    for chapter in chapters:
        session_number = chapter["session_number"]
        title = chapter["title"]
        paragraphs = chapter["text"]

        # Chapter Cover Page
        elements.append(Paragraph(f"Chapter {session_number}", centered_style))
        elements.append(Spacer(1, 20))

        if session_number in images:
            img = Image(images[session_number])
            max_width, max_height = 6.5 * inch, 9 * inch
            img.drawWidth, img.drawHeight = (
                max_width,
                img.imageHeight * (max_width / img.imageWidth),
            )
            if img.drawHeight > max_height:
                img.drawWidth, img.drawHeight = (
                    img.imageWidth * (max_height / img.imageHeight),
                    max_height,
                )
            elements.append(img)
            elements.append(Spacer(1, 20))

        elements.append(Paragraph(title, centered_style))
        elements.append(PageBreak())

        # Chapter Text with additional images every 5 paragraphs
        for i, paragraph in enumerate(paragraphs):
            elements.append(Paragraph(paragraph, body_text_style))
            elements.append(Spacer(1, 12))
            if (i + 1) % 5 == 0:
                additional_prompt = f"Illustration based on: {paragraph}"
                additional_image = generate_image(
                    additional_prompt,
                    f"chapter_{session_number}_extra_{i // 5 + 1}",
                    "images",
                )
                img = Image(additional_image)
                img.drawWidth, img.drawHeight = (
                    max_width,
                    img.imageHeight * (max_width / img.imageWidth),
                )
                elements.append(img)
                elements.append(Spacer(1, 20))

        elements.append(PageBreak())

    pdf.build(elements)
    print(f"PDF created at: {output_path}")


def process_files(input_dir, image_dir, json_path, output_pdf):
    """
    Processes text files and JSON configuration to create a narrative PDF.
    """
    story_details = read_story_details(json_path)
    chapters = []

    for file_name in os.listdir(input_dir):
        if file_name.startswith("session_") and file_name.endswith(".txt"):
            session_number = int(file_name.split("_")[1].split(".")[0])

            with open(os.path.join(input_dir, file_name), "r") as f:
                lines = f.readlines()
                if len(lines) < 2:
                    print(f"File {file_name} does not have enough lines.")
                    continue

                title_line = lines[0].strip()
                title = title_line.split(":", 1)[1].strip()
                chapter_text = "".join(lines[1:]).strip()

                print(f"Generating text for Chapter {session_number}: {title}")
                paragraphs = generate_text(chapter_text, story_details)

                chapters.append(
                    {
                        "session_number": session_number,
                        "title": title,
                        "text": paragraphs,
                    }
                )

    chapters.sort(key=lambda x: x["session_number"])

    images = {}
    for chapter in chapters:
        session_number = chapter["session_number"]
        title = chapter["title"]
        prompt = f"Illustration for Chapter {session_number}: {title}"
        images[session_number] = generate_image(
            prompt, f"chapter_{session_number}", image_dir
        )

    create_pdf(chapters, images, output_pdf)


if __name__ == "__main__":
    input_directory = "transcripts"
    image_directory = "images"
    json_file_path = "story_details.json"
    output_pdf_path = "dnd_storybook.pdf"

    process_files(input_directory, image_directory, json_file_path, output_pdf_path)
