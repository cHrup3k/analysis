from pathlib import Path

def recordings(root: Path):
    return sorted(p for p in root.iterdir() if p.is_dir() and p.name!='analysis_results' and
                  (any(p.glob('mic*.pdm')) or (p/'capture_udp_interleaved.bin').exists()))
