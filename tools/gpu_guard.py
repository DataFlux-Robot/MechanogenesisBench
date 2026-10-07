#!/usr/bin/env python3
"""GPU cleanup guard: kill lingering processes before merge/training."""
import subprocess, time, sys

def gpu_used_mb():
    r = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                       capture_output=True, text=True)
    return int(r.stdout.strip().split('\n')[0])

def kill_gpu_hogs():
    r = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,used_memory', '--format=csv,noheader'],
                       capture_output=True, text=True)
    for line in r.stdout.strip().split('\n'):
        if not line.strip(): continue
        parts = [p.strip() for p in line.split(',')]
        pid, mem = parts[0], parts[1]
        if int(mem.replace(' MiB','').replace(',','')) > 500:  # skip gnome-remote-desktop
            try:
                subprocess.run(['kill', '-9', pid], capture_output=True)
                print(f"  killed {pid} ({mem})")
            except: pass

def ensure_clean(max_mb=2000, timeout=30):
    t0 = time.time()
    while gpu_used_mb() > max_mb and time.time() - t0 < timeout:
        kill_gpu_hogs()
        time.sleep(3)
    mb = gpu_used_mb()
    if mb > max_mb:
        print(f"WARNING: GPU still at {mb}MB after cleanup")
        return False
    return True

if __name__ == '__main__':
    ok = ensure_clean()
    print(f"GPU: {gpu_used_mb()}MB {'CLEAN' if ok else 'DIRTY'}")
    sys.exit(0 if ok else 1)
