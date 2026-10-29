import numpy as np
import pytest
from PIL import Image

from app.reference import BBox, GRAY, build_reference_canvas


def test_only_selected_position_changes(tmp_path):
    photo = tmp_path / "photo.png"
    Image.new("RGB", (80, 40), (240, 50, 10)).save(photo)
    result = build_reference_canvas(photo, tmp_path / "canvas.png", BBox(50, 30, 20, 24), 128, 96,
                                    photo_bbox=BBox(10, 0, 40, 40))
    canvas = np.array(Image.open(result.path))
    assert canvas.shape == (96, 128, 3)
    assert np.all(canvas[30:54, 50:70] == [240, 50, 10])
    canvas[30:54, 50:70] = GRAY
    assert np.all(canvas == GRAY)
    assert result.frame_idx == -1


@pytest.mark.parametrize("box", [BBox(-1, 0, 20, 20), BBox(0, 0, 0, 20), BBox(120, 0, 20, 20)])
def test_invalid_bbox_fails_before_writing(tmp_path, box):
    with pytest.raises(ValueError):
        build_reference_canvas(tmp_path / "missing.jpg", tmp_path / "out.png", box, 128, 96)
    assert not (tmp_path / "out.png").exists()


def test_multiple_reference_faces_require_selection(tmp_path, monkeypatch):
    photo = tmp_path / "photo.png"
    Image.new("RGB", (80, 80)).save(photo)
    monkeypatch.setattr("app.reference.detect_faces", lambda _: [BBox(0, 0, 20, 20), BBox(30, 30, 20, 20)])
    with pytest.raises(ValueError, match="Multiple faces"):
        build_reference_canvas(photo, tmp_path / "out.png", BBox(0, 0, 20, 20), 128, 96)


def test_fallback_is_explicit_and_png(tmp_path, monkeypatch):
    photo = tmp_path / "photo.jpg"
    Image.new("RGB", (80, 40), (200, 20, 10)).save(photo)
    monkeypatch.setattr("app.reference.detect_faces", lambda _: [])
    result = build_reference_canvas(photo, tmp_path / "out.png", BBox(5, 5, 30, 30), 128, 96)
    assert result.crop_method == "center_fallback"
    assert result.photo_bbox == BBox(20, 0, 40, 40)
    assert Image.open(result.path).format == "PNG"


def test_exif_orientation_is_applied(tmp_path):
    photo = tmp_path / "photo.jpg"
    image = Image.new("RGB", (80, 40), (200, 20, 10))
    exif = image.getexif()
    exif[274] = 6
    image.save(photo, exif=exif)
    result = build_reference_canvas(photo, tmp_path / "out.png", BBox(5, 5, 30, 30), 128, 96,
                                    photo_bbox=BBox(0, 0, 40, 80))
    assert result.photo_bbox.height == 80


def test_expand_grows_crop_and_target_around_centre(tmp_path):
    photo = tmp_path / "photo.png"
    image = Image.new("RGB", (100, 100), (0, 0, 255))
    image.paste((240, 50, 10), (30, 30, 70, 70))
    image.save(photo)
    result = build_reference_canvas(photo, tmp_path / "canvas.png", BBox(40, 30, 40, 40), 128, 96,
                                    photo_bbox=BBox(30, 30, 40, 40), expand=1.5)
    canvas = np.array(Image.open(result.path))
    assert np.all(canvas[30:70, 40:80] == [240, 50, 10])  # face itself stays at the selected box
    assert np.all(canvas[22:28, 32:88] == [0, 0, 255])    # surrounding photo context fills the grown box
    assert np.all(canvas[:20] == GRAY)
    assert result.target_bbox == BBox(40, 30, 40, 40)


def test_expand_out_of_range_rejected(tmp_path):
    with pytest.raises(ValueError, match="expand"):
        build_reference_canvas(tmp_path / "p.png", tmp_path / "o.png", BBox(0, 0, 20, 20), 128, 96, expand=0.5)
