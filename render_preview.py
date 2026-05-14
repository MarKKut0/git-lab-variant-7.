"""
Multi-view PNG preview всех STL.
Использует trimesh + matplotlib (без OpenGL).
"""
from pathlib import Path
import numpy as np
import trimesh
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def render_mesh(mesh: trimesh.Trimesh, ax, view: str, color="#c9a37e"):
    """Рисует mesh в matplotlib 3D axes под заданной проекцией."""
    verts = mesh.vertices[mesh.faces]
    coll = Poly3DCollection(verts, alpha=0.95, linewidths=0.15)
    coll.set_facecolor(color)
    coll.set_edgecolor((0.2, 0.15, 0.1, 0.4))
    ax.add_collection3d(coll)

    bb_min, bb_max = mesh.bounds
    center = (bb_min + bb_max) / 2
    size = (bb_max - bb_min).max() * 0.6

    ax.set_xlim(center[0] - size, center[0] + size)
    ax.set_ylim(center[1] - size, center[1] + size)
    ax.set_zlim(center[2] - size, center[2] + size)

    views = {
        "iso":   (25, -55),
        "front": (0, -90),
        "side":  (0, 0),
        "top":   (89, -90),
    }
    elev, azim = views.get(view, (25, -55))
    ax.view_init(elev=elev, azim=azim)
    ax.set_box_aspect([1, 1, 1])
    ax.set_axis_off()
    ax.set_title(view, fontsize=10)


def make_multi_view(stl_path: Path, out_png: Path, color="#c9a37e", title=None):
    mesh = trimesh.load(stl_path, force="mesh")
    fig = plt.figure(figsize=(11, 9), facecolor="white")
    fig.suptitle(title or stl_path.stem, fontsize=13, y=0.97)
    for i, view in enumerate(["iso", "front", "side", "top"], start=1):
        ax = fig.add_subplot(2, 2, i, projection="3d")
        render_mesh(mesh, ax, view, color=color)
    fig.tight_layout()
    fig.savefig(out_png, dpi=110, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def make_assembly_view(stl_path: Path, out_png: Path):
    """Особый вид для assembly: 4 ракурса побольше."""
    mesh = trimesh.load(stl_path, force="mesh")
    fig = plt.figure(figsize=(13, 11), facecolor="white")
    fig.suptitle("birdhouse — assembly preview", fontsize=14, y=0.97)
    for i, view in enumerate(["iso", "front", "side", "top"], start=1):
        ax = fig.add_subplot(2, 2, i, projection="3d")
        render_mesh(mesh, ax, view, color="#b07a4d")
    fig.tight_layout()
    fig.savefig(out_png, dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def watertight_check(stl_path: Path) -> tuple[bool, dict]:
    mesh = trimesh.load(stl_path, force="mesh")
    info = {
        "watertight": bool(mesh.is_watertight),
        "volume_cm3": float(mesh.volume) / 1000.0 if mesh.is_watertight else None,
        "bbox_mm": [round(float(x), 2) for x in (mesh.bounds[1] - mesh.bounds[0])],
        "faces": int(len(mesh.faces)),
    }
    return mesh.is_watertight, info


if __name__ == "__main__":
    import sys
    # Импортируем VERSION из birdhouse.py
    sys.path.insert(0, str(Path(__file__).parent))
    from birdhouse import VERSION
    out = Path.home() / "Downloads" / f"birdhouse_v{VERSION}"
    previews = out / "previews"
    previews.mkdir(parents=True, exist_ok=True)

    print("Validation per part:")
    print("-" * 70)
    for stl in sorted(out.glob("birdhouse_*.stl")):
        ok, info = watertight_check(stl)
        flag = "OK" if ok else "FAIL"
        bbox = info["bbox_mm"]
        vol = f"{info['volume_cm3']:.1f} cm3" if info["volume_cm3"] is not None else "n/a"
        print(f"  [{flag}] {stl.name:40s} bbox={bbox} vol={vol} faces={info['faces']}")

    print("\nRendering previews...")
    for stl in sorted(out.glob("birdhouse_*.stl")):
        png = previews / f"{stl.stem}.png"
        if "assembly" in stl.stem:
            make_assembly_view(stl, png)
        else:
            make_multi_view(stl, png, title=stl.stem)
        print(f"  -> {png.name}")

    print(f"\nPreviews in: {previews}")
