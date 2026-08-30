import os
import json
import requests
from PIL import Image
from io import BytesIO
from datetime import datetime
from app.utils import logger, get_safe_newspaper_dir

def download_images(
    date_str: str,
    post_title: str,
    post_url: str,
    post_id: str,
    image_urls: list,
    cookies: list,
    expected_count: int = 30,
    min_count: int = 28
) -> dict:
    """
    Downloads image URLs sequentially (01.jpg, 02.jpg, ...), verifying each file.
    Saves metadata.json. Re-tries failed images if executed again.
    """
    target_dir = get_safe_newspaper_dir(date_str)
    metadata_path = os.path.join(target_dir, "metadata.json")

    # Load existing metadata if available to check status
    existing_metadata = {}
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                existing_metadata = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read existing metadata: {e}")

    # Setup HTTP Session with browser cookies and referer headers
    session = requests.Session()
    # Replicate browser cookies
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', ''))

    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://cafe.naver.com/",
    })

    total_images = len(image_urls)
    logger.info(f"Starting download of {total_images} images to {target_dir}")

    success_count = 0
    download_details = []

    for idx, url in enumerate(image_urls, start=1):
        # Detect file extension from URL
        url_lower = url.lower().split("?")[0]
        if url_lower.endswith(".gif"):
            ext = "gif"
        elif url_lower.endswith(".png"):
            ext = "png"
        else:
            ext = "jpg"
        filename = f"{idx:02d}.{ext}"
        file_path = os.path.join(target_dir, filename)

        # Check if the file is already downloaded and valid
        is_valid = False
        if os.path.exists(file_path):
            try:
                with Image.open(file_path) as img:
                    img.verify()
                is_valid = True
            except Exception:
                logger.warning(f"Existing file {filename} is corrupt. Redownloading...")
                try:
                    os.remove(file_path)
                except OSError:
                    pass

        if is_valid:
            logger.info(f"Image {filename} already exists and is valid. Skipping.")
            success_count += 1
            download_details.append({"filename": filename, "status": "success", "cached": True})
            continue

        # Download image
        try:
            response = session.get(url, timeout=15)
            response.raise_for_status()

            # Verify it is a valid image using Pillow
            image_data = response.content
            img = Image.open(BytesIO(image_data))
            img.verify()

            # Save the raw bytes directly to preserve original quality and format
            with open(file_path, 'wb') as f:
                f.write(image_data)

            logger.info(f"Successfully downloaded {filename}")
            success_count += 1
            download_details.append({"filename": filename, "status": "success", "cached": False})
        except Exception as e:
            logger.error(f"Failed to download image {idx} from {url}: {e}")
            download_details.append({"filename": filename, "status": "failed", "error": str(e)})

    # Verification
    status = "success"
    if success_count < total_images:
        status = "failed"
        logger.warning(f"Download completed with failures: {success_count}/{total_images} succeeded.")
    elif success_count < min_count:
        status = "failed"
        logger.error(f"Downloaded only {success_count} images, which is less than the minimum required {min_count}.")
    else:
        logger.info(f"Successfully completed download: {success_count}/{total_images} images.")

    metadata = {
        "date": date_str,
        "title": post_title,
        "post_url": post_url,
        "post_id": post_id,
        "image_count": total_images,
        "downloaded_count": success_count,
        "download_time": datetime.now().isoformat(),
        "status": status,
        "downloads": download_details
    }

    # Save metadata.json
    try:
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to write metadata.json: {e}")

    return metadata
