# Oil Pastel Patch Painter

Turn a photo into a textured oil-pastel artwork. The renderer builds the image
in broad, mid-tone, and detail passes so the process can be watched as a
patch-by-patch painting.

## Requirements

- Python 3.9+
- OpenCV
- NumPy

Install the dependencies:

```bash
python -m pip install opencv-python numpy
```

## Usage

Paint an image with a live progress window:

```bash
python oil_pastel_patches.py photo.jpg
```

Create a headless output:

```bash
python oil_pastel_patches.py photo.jpg --no-window --seed 42
```

Create a time-lapse video:

```bash
python oil_pastel_patches.py photo.jpg --video timelapse.mp4 --speed 4
```

Useful options:

| Option | Description |
| --- | --- |
| `-o`, `--out PATH` | Final framed image path. Defaults to `<input>_oilpastel.png`. |
| `--size N` | Longest artwork side in pixels. Defaults to `900`. |
| `--speed N` | Patches painted per displayed video/window frame. Defaults to `3`. |
| `--density N` | Stroke-density multiplier. Higher values add more pigment. |
| `--seed N` | Reproduce the same painting on later runs. |
| `--video PATH` | Save an MP4 of the patch-by-patch process. |
| `--fps N` | Time-lapse frame rate. Defaults to `30`. |
| `--no-window` | Disable the live window for servers and scripts. |

During the live preview, use:

- **Space** to pause or resume
- **S** to save a numbered snapshot
- **Q** or **Esc** to stop early

## Output files

For an output path such as `photo_oilpastel.png`, the script writes:

- `photo_oilpastel.png` — the final framed artwork
- `photo_oilpastel_artwork_only.png` — the artwork without the desk, tape, and frame
- `photo_oilpastel_patches.png` — a patch map with numbered, colored boundaries
- `photo_oilpastel_snap<N>.png` — optional snapshots saved with **S**
- the requested MP4 — progress frames also include the visible patch map

Patch colors identify their painting pass. The numbered circles show the order
in which patches were completed, making the generated process inspectable even
when the script is run with `--no-window`.

## Development

Run the tests with Python's standard-library test runner:

```bash
python -m unittest -v
```

The test suite covers patch tracking and the visibility overlay without
requiring a GUI.
