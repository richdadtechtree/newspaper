import os
import json
from PIL import Image
from app.utils import logger, get_safe_newspaper_dir


def build_pdf(date_str: str, image_filenames: list) -> str:
    """
    Merges downloaded newspaper images (already in page order) into a single
    multi-page PDF. Returns the path to the generated PDF.
    """
    target_dir = get_safe_newspaper_dir(date_str)
    pdf_path = os.path.join(target_dir, f"{date_str}.pdf")

    if not image_filenames:
        raise ValueError("PDF로 만들 이미지가 없습니다.")

    images = []
    try:
        for filename in image_filenames:
            file_path = os.path.join(target_dir, filename)
            img = Image.open(file_path)
            if img.mode != "RGB":
                img = img.convert("RGB")
            images.append(img)

        first, rest = images[0], images[1:]
        first.save(pdf_path, save_all=True, append_images=rest)
    finally:
        for img in images:
            img.close()

    logger.info(f"PDF 생성 완료: {pdf_path} ({len(image_filenames)}페이지)")
    return pdf_path


def ensure_pdf(date_str: str):
    """
    Builds the PDF for date_str from the images already recorded in
    metadata.json, unless a valid PDF already exists. Updates metadata.json
    with the result. Returns the PDF path, or None if there is nothing to
    build from (no metadata yet, or no successfully downloaded images).
    """
    target_dir = get_safe_newspaper_dir(date_str)
    metadata_path = os.path.join(target_dir, "metadata.json")

    if not os.path.exists(metadata_path):
        logger.warning(f"{date_str}의 metadata.json이 없어 PDF를 생성할 수 없습니다.")
        return None

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    pdf_path = os.path.join(target_dir, f"{date_str}.pdf")
    if metadata.get("pdf_status") == "success" and os.path.exists(pdf_path):
        logger.info(f"이미 생성된 PDF가 있어 건너뜁니다: {pdf_path}")
        return pdf_path

    filenames = [
        d["filename"] for d in metadata.get("downloads", [])
        if d.get("status") == "success"
    ]

    if not filenames:
        logger.warning("성공적으로 다운로드된 이미지가 없어 PDF를 생성할 수 없습니다.")
        return None

    built_path = build_pdf(date_str, filenames)

    metadata["pdf_path"] = os.path.basename(built_path)
    metadata["pdf_status"] = "success"
    metadata["pdf_page_count"] = len(filenames)

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    return built_path
