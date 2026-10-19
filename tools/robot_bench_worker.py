#!/usr/bin/env python3
"""Robot Bench worker — second execution domain (simulated legged body design).

Takes a morphology design JSON (lower_leg_extension_m in [-0.003, 0.008]),
builds the MJCF through the FluxKernel morphology pipeline (replay_variant),
runs a reduced MuJoCo acceptance subset (stand + forward 0.1 m/s, 3 seeds x 2
worlds) with a frozen locomotion policy, and returns gate metrics.

Run with the microduck runtime venv:
  unset PYTHONPATH
  WANDB_MODE=disabled HF_HUB_OFFLINE=1 CUDA_VISIBLE_DEVICES=0 \
  /home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/microduck-rl-runtime/.venv/bin/python \
    tools/robot_bench_worker.py --design design.json --checkpoint <model_5199.pt> --out result.json
"""
import os
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("WANDB_MODE", "disabled")
os.environ.setdefault("WANDB_DISABLED", "true")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("PYTHONUNBUFFERED", "1")

import argparse, gc, hashlib, json, sys, time
from dataclasses import asdict
from pathlib import Path

import numpy as np

AUTORESEARCH = Path('/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH')
FLUX_ROOT = AUTORESEARCH / 'fluxkernel-body-control'
BASE_BUNDLE = AUTORESEARCH / 'fluxkernel/.demo/v012-lossless-final/microduck/restored'
BASE_NATIVE_SHA256 = '8795d7f3594e388468791b15f597534c15fe533d2f1cc9501e9cd6e1d80b94ee'
BASE_MJCF_SHA256 = 'a6e41f90c19d8f471eb261c5564d3a2e0c1b7e82ef92d2dbee8f74fe6f8d7db2'

sys.path.insert(0, str(FLUX_ROOT))
from fluxkernel.robotics import morphology
from fluxkernel.robotics.native import read as read_native, digest as native_digest, plant, validate
from fluxkernel.robotics.projection import mjcf
from fluxkernel.robotics.sources import safe

assert '/fluxkernel-body-control/' in morphology.__file__, morphology.__file__

import torch
import mujoco
import mjlab_microduck.tasks  # noqa: F401 registers the task
from mjlab.tasks.registry import load_env_cfg, load_rl_cfg, load_runner_cls
from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import RslRlVecEnvWrapper

TASK = 'Mjlab-Velocity-Flat-MicroDuck'
SEEDS = (20260929, 20260930, 20260931)
CASES = ({'name': 'stand', 'command': (0.0, 0.0, 0.0)},
         {'name': 'forward_010', 'command': (0.1, 0.0, 0.0)})
WORLDS = 2
DURATION_S = 30.0
WARMUP_S = 2.0
SPAWN_Z_BASE = 0.125
GATE = {
    'minTrialPassFraction': 0.95, 'fallMinRootHeightM': 0.06, 'fallMinUpright': 0.5,
    'speedRatioMin': 0.6, 'speedRatioMax': 1.4, 'maxVelocityXyRmseMps': 0.1,
    'maxMeanLateralVelocityMps': 0.05, 'maxYawRmseRadps': 0.35,
    'maxStandingDriftM': 0.25, 'maxTurningDriftM': 0.4, 'maxStanceSlipMps': 0.08,
    'minFootContactTransitions': 10, 'maxJointLimitViolationFraction': 0.01,
    'jointLimitToleranceRad': 0.01,
}


def build_variant(design, out_dir):
    params = morphology.checked_parameters(design)
    base = read_native(BASE_BUNDLE)
    if native_digest(base) != BASE_NATIVE_SHA256:
        raise ValueError('base native digest mismatch')
    if hashlib.sha256((BASE_BUNDLE / 'robot.xml').read_bytes()).hexdigest() != BASE_MJCF_SHA256:
        raise ValueError('base MJCF digest mismatch')
    leg = next(m for m in base['meshes'] if m['name'] == 'leg')
    raw = safe(BASE_BUNDLE, leg['file']).read_bytes()
    replay = morphology.replay_variant(base, raw, params)
    out_dir.mkdir(parents=True, exist_ok=False)
    for m in replay['robot']['meshes']:
        dst = out_dir / m['file']
        dst.parent.mkdir(parents=True, exist_ok=True)
        if m['name'] == 'leg':
            dst.write_bytes(replay['leg_mesh_bytes'])
        else:
            dst.write_bytes(safe(BASE_BUNDLE, m['file']).read_bytes())
    mjcf(replay['robot'], out_dir / 'robot.xml')
    return out_dir / 'robot.xml', replay, params


# ── 8-parameter numeric design space via bundle.revise semantics (fast path:
# in-memory edit + validate, no Lean finish) ──
REVISE_BOUNDS = {
    'trunk_mass_scale': (0.95, 1.05), 'trunk_com_x_m': (-0.003, 0.003),
    'upper_leg_mass_scale': (0.90, 1.10), 'lower_leg_mass_scale': (0.90, 1.10),
    'head_mass_scale': (0.90, 1.10), 'hip_range_scale': (0.85, 1.00),
    'knee_ankle_range_scale': (0.85, 1.00), 'leg_range_center_shift_rad': (-0.05, 0.05),
}
REVISE_GROUPS = {
    'trunk_mass_scale': ('trunk_base',),
    'upper_leg_mass_scale': ('upper_leg_left', 'upper_leg_right'),
    'lower_leg_mass_scale': ('leg', 'leg_2', 'ankle_left', 'ankle_right'),
    'head_mass_scale': ('neck', 'neck_pitch', 'yaw_roll_motion', 'jaw_soft'),
}
HIP_JOINTS = ('left_hip_yaw', 'left_hip_roll', 'left_hip_pitch',
              'right_hip_yaw', 'right_hip_roll', 'right_hip_pitch')
KNEE_ANKLE_JOINTS = ('left_knee', 'left_ankle', 'right_knee', 'right_ankle')


def checked_revise(design):
    import math
    if not isinstance(design, dict) or set(design) != set(REVISE_BOUNDS):
        raise ValueError('revise design keys must be exactly ' + ', '.join(REVISE_BOUNDS))
    out = {}
    for k, (lo, hi) in REVISE_BOUNDS.items():
        v = design[k]
        if type(v) not in (int, float) or not math.isfinite(v) or not lo <= v <= hi:
            raise ValueError(f'{k} must be finite in [{lo}, {hi}]')
        out[k] = float(v)
    return out


def build_revise(design, out_dir):
    import copy
    params = checked_revise(design)
    base = read_native(BASE_BUNDLE)
    if native_digest(base) != BASE_NATIVE_SHA256:
        raise ValueError('base native digest mismatch')
    child = copy.deepcopy(base)
    bodies = {b['name']: b for b in child['bodies']}
    joints = {j['name']: j for j in child['joints']}
    for key, names in REVISE_GROUPS.items():
        s = params[key]
        for name in names:
            b = bodies[name]
            b['mass'] = b.get('mass', 0.0) * s
            b['principal_inertia'] = [x * s for x in b.get('principal_inertia', [0, 0, 0])]
    ip = list(bodies['trunk_base']['inertial_position'])
    ip[0] += params['trunk_com_x_m']
    bodies['trunk_base']['inertial_position'] = ip
    for names, key in ((HIP_JOINTS, 'hip_range_scale'), (KNEE_ANKLE_JOINTS, 'knee_ankle_range_scale')):
        for name in names:
            j = joints[name]
            r = list(j['range'])
            c = params['leg_range_center_shift_rad']
            j['range'] = [r[0] * params[key] + c, r[1] * params[key] + c]
    child['controller']['plant_sha256'] = plant(child)
    child['controller']['status'] = 'requires-revalidation'
    child['controller']['deployment_ready'] = False
    validate(child)
    out_dir.mkdir(parents=True, exist_ok=False)
    for m in child['meshes']:
        dst = out_dir / m['file']
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(safe(BASE_BUNDLE, m['file']).read_bytes())
    mjcf(child, out_dir / 'robot.xml')
    return out_dir / 'robot.xml', child, params


def validate_mjcf(xml):
    model = mujoco.MjModel.from_xml_path(str(xml))
    assert model.nq == 21 and model.nv == 20 and model.nu == 14, (model.nq, model.nv, model.nu)
    joints = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i) for i in range(model.njnt)]
    assert joints[:5] == ['trunk_base_freejoint', 'left_hip_yaw', 'left_hip_roll',
                          'left_hip_pitch', 'left_knee']
    sites = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_SITE, i) for i in range(model.nsite)]
    assert 'left_foot' in sites and 'right_foot' in sites
    return model


def make_env(xml_path, seed, extension, device='cuda:0'):
    cfg = load_env_cfg(TASK, play=True)
    cfg.seed = seed
    cfg.scene.num_envs = len(CASES) * WORLDS
    cfg.auto_reset = False
    cfg.terminations = {}
    cfg.curriculum = {}
    cfg.events = {k: v for k, v in cfg.events.items() if v.mode != 'interval'}
    spawn_z = SPAWN_Z_BASE + extension
    cfg.events['reset_base'].params['pose_range'] = {
        'x': (0.0, 0.0), 'y': (0.0, 0.0), 'z': (spawn_z, spawn_z),
        'roll': (0.0, 0.0), 'pitch': (0.0, 0.0), 'yaw': (0.0, 0.0)}
    cfg.events['reset_base'].params['velocity_range'] = {}
    cmd = cfg.commands['twist']
    for attr in ('rel_standing_envs', 'rel_heading_envs', 'rel_world_envs',
                 'rel_forward_envs', 'rel_turn_in_place_envs', 'init_velocity_prob'):
        if hasattr(cmd, attr):
            setattr(cmd, attr, 0.0)
    cmd.resampling_time_range = (10000.0, 10000.0)
    for name in ('head_pose', 'body_pose'):
        cfg.commands[name].ranges = tuple((0.0, 0.0) for _ in cfg.commands[name].ranges)
        cfg.commands[name].resampling_time_range = (10000.0, 10000.0)
    cfg.scene.entities['robot'].spec_fn = lambda: mujoco.MjSpec.from_file(str(xml_path))
    return ManagerBasedRlEnv(cfg, device=device)


def make_policy(env, checkpoint, device='cuda:0'):
    agent = load_rl_cfg(TASK)
    wrapped = RslRlVecEnvWrapper(env, clip_actions=agent.clip_actions)
    runner = load_runner_cls(TASK)(wrapped, asdict(agent), device=device)
    runner.load(str(checkpoint), load_cfg={'actor': True}, strict=True, map_location=device)
    return wrapped, runner, runner.get_inference_policy(device=device)


def inject_commands(wrapped):
    env = wrapped.unwrapped
    commands_np = [c['command'] for c in CASES for _ in range(WORLDS)]
    commands = torch.tensor(commands_np, device=env.device)
    twist = env.command_manager.get_term('twist')
    twist.vel_command_b.copy_(commands)
    twist.vel_command_w.copy_(commands)
    for attr in ('is_standing_env', 'is_heading_env', 'is_world_env', 'is_forward_env'):
        getattr(twist, attr).fill_(False)
    twist.time_left.fill_(10000)
    obs = wrapped.get_observations()
    assert tuple(obs['actor'].shape) == (env.num_envs, 61), obs['actor'].shape
    assert wrapped.num_actions == 14
    return twist, commands, obs


def run_seed(xml_path, checkpoint, seed, extension, device='cuda:0'):
    env = make_env(xml_path, seed, extension, device)
    try:
        wrapped, runner, policy = make_policy(env, checkpoint, device)
        twist, commands, obs = inject_commands(wrapped)
        robot = env.scene['robot']
        siteids, _ = robot.find_sites(['left_foot', 'right_foot'], preserve_order=True)
        dt = env.step_dt
        steps = round(DURATION_S / dt)
        initial = robot.data.root_link_pose_w.cpu().numpy().copy()
        raw = {k: [] for k in ('pose', 'vel_b', 'yaw_rate', 'upright', 'contact',
                               'foot_speed', 'force', 'limit_violation', 'done', 'command')}
        with torch.inference_mode():
            for t in range(steps):
                actions = policy(obs)
                obs, _, done, _ = wrapped.step(actions)
                d = robot.data
                pose = d.root_link_pose_w
                force = d.actuator_force
                if not bool(torch.isfinite(pose).all() & torch.isfinite(d.joint_pos).all()
                            & torch.isfinite(d.joint_vel).all() & torch.isfinite(force).all()):
                    raise RuntimeError(f'Nonfinite physics seed={seed} step={t}')
                assert not bool(done.any())
                assert bool(torch.allclose(twist.command, commands))
                limits = d.joint_pos_limits
                violation = ((d.joint_pos < limits[..., 0] - GATE['jointLimitToleranceRad'])
                             | (d.joint_pos > limits[..., 1] + GATE['jointLimitToleranceRad'])).any(dim=-1)
                vals = {
                    'pose': pose, 'vel_b': d.root_link_lin_vel_b,
                    'yaw_rate': d.root_link_ang_vel_b[:, 2],
                    'upright': -d.projected_gravity_b[:, 2],
                    'contact': env.scene['feet_ground_contact'].data.found.reshape(env.num_envs, 2, -1).any(dim=-1),
                    'foot_speed': d.site_lin_vel_w[:, siteids, :2].norm(dim=-1),
                    'force': force, 'limit_violation': violation, 'done': done,
                    'command': twist.command}
                for k, v in vals.items():
                    raw[k].append(v.cpu().numpy().copy())
        raw = {k: np.stack(v) for k, v in raw.items()}
        raw['dt'] = np.array(dt)
        raw['initial_pose'] = initial
        raw['seed'] = np.array(seed)
        return summarize(raw, seed)
    finally:
        try:
            env.close()
        except Exception:
            pass
        gc.collect()
        torch.cuda.empty_cache()


def summarize(raw, seed):
    dt = float(raw['dt'])
    start = round(WARMUP_S / dt)
    rows = []
    for i in range(len(CASES) * WORLDS):
        case = CASES[i // WORLDS]
        cmd = np.array(case['command'], dtype=float)
        vel = raw['vel_b'][start:, i]
        yaw = raw['yaw_rate'][start:, i]
        contact = raw['contact'][:, i]
        xy = raw['pose'][:, i, :2]
        drift = np.linalg.norm(xy - raw['initial_pose'][i, :2], axis=-1)
        falls = ((raw['pose'][:, i, 2] < GATE['fallMinRootHeightM'])
                 | (raw['upright'][:, i] < GATE['fallMinUpright']))
        transitions = np.count_nonzero(np.diff(contact.astype(int), axis=0), axis=0)
        c = contact[start:]
        slip = float((raw['foot_speed'][start:, i] * c).sum() / max(1, c.sum()))
        meanvel = vel.mean(axis=0)
        xyrmse = float(np.sqrt(np.mean(np.sum((vel[:, :2] - cmd[:2]) ** 2, axis=-1))))
        yrmse = float(np.sqrt(np.mean((yaw - cmd[2]) ** 2)))
        violation = float(raw['limit_violation'][:, i].mean())
        force = float(np.max(np.abs(raw['force'][:, i])))
        gates = {
            'fall_free': not bool(falls.any()),
            'xy_tracking': xyrmse <= GATE['maxVelocityXyRmseMps'],
            'yaw_tracking': yrmse <= GATE['maxYawRmseRadps'],
            'joint_limits': violation <= GATE['maxJointLimitViolationFraction'],
            'actuation': force > 1e-6,
            'stance_slip': slip <= GATE['maxStanceSlipMps'],
        }
        if cmd[0] != 0:
            gates['forward_speed'] = GATE['speedRatioMin'] <= meanvel[0] / cmd[0] <= GATE['speedRatioMax']
            gates['lateral_drift'] = abs(meanvel[1]) <= GATE['maxMeanLateralVelocityMps']
            gates['stepping'] = transitions.min() >= GATE['minFootContactTransitions']
        elif cmd[2] != 0:
            gates['turn_rate'] = GATE['speedRatioMin'] <= yaw.mean() / cmd[2] <= GATE['speedRatioMax']
            gates['turn_drift'] = drift.max() <= GATE['maxTurningDriftM']
            gates['stepping'] = transitions.min() >= GATE['minFootContactTransitions']
        else:
            gates['standing_drift'] = drift.max() <= GATE['maxStandingDriftM']
        rows.append({'seed': int(seed), 'case': case['name'], 'environment': i,
                     'command': list(cmd), 'meanVx': float(meanvel[0]),
                     'meanVy': float(meanvel[1]), 'meanYawRate': float(yaw.mean()),
                     'xyRmse': xyrmse, 'yawRmse': yrmse, 'stanceSlip': slip,
                     'maxPlanarDrift': float(drift.max()), 'fall': bool(falls.any()),
                     'minUpright': float(raw['upright'][:, i].min()),
                     'contactTransitions': [int(x) for x in transitions],
                     'jointLimitViolationFraction': violation,
                     'maxActuatorForce': force,
                     'pass': all(gates.values()), 'gates': {k: bool(v) for k, v in gates.items()}})
    return rows


def main():
    global CASES
    ap = argparse.ArgumentParser()
    ap.add_argument('--design', required=True, help='JSON file or inline JSON')
    ap.add_argument('--checkpoint', required=True)
    ap.add_argument('--out', default='')
    ap.add_argument('--workdir', default='')
    ap.add_argument('--demand', type=float, default=0.1, help='target forward speed m/s')
    ap.add_argument('--yaw', type=float, default=0.0, help='target yaw rate rad/s')
    ap.add_argument('--forward-only', action='store_true', help='skip the stand case')
    ap.add_argument('--revise', action='store_true',
                    help='8-parameter numeric design space (mass/inertia/COM/joint-range edits)')
    a = ap.parse_args()
    if a.forward_only:
        CASES = (CASES[1],)
    if a.demand != 0.1 or a.yaw != 0.0:
        CASES = tuple({'name': (f'forward_{a.demand:.2f}' if a.yaw == 0.0 else f'turn_{a.yaw:.2f}'),
                       'command': (a.demand, 0.0, a.yaw) if c['name'] == 'forward_010' else (0.0, 0.0, 0.0)}
                      for c in CASES)
    t0 = time.monotonic()
    try:
        d = Path(a.design)
        design = json.loads(d.read_text()) if d.exists() else json.loads(a.design)
        if not a.revise and 'lower_leg_extension_m' not in design:
            raise ValueError('design must contain lower_leg_extension_m')
        work = Path(a.workdir) if a.workdir else (AUTORESEARCH / 'MechanogenesisBench-upstream'
                                                  / 'runs' / 'robot_bench' / f"design_{int(time.time()*1000)}")
        if a.revise:
            xml, body_ir, params = build_revise(design, work)
            ext = 0.0
        else:
            xml, replay, params = build_variant(design, work)
            body_ir = replay['robot']
            ext = float(params['lower_leg_extension_m'])
        model = validate_mjcf(xml)
        trials = []
        for seed in SEEDS:
            trials += run_seed(xml, a.checkpoint, seed, ext)
        cases = []
        for case in CASES:
            rs = [r for r in trials if r['case'] == case['name']]
            passed = sum(1 for r in rs if r['pass'])
            cases.append({'case': case['name'], 'command': list(case['command']),
                          'trials': len(rs), 'passed': passed,
                          'falls': sum(1 for r in rs if r['fall']),
                          'meanVx': float(np.mean([r['meanVx'] for r in rs])),
                          'meanVy': float(np.mean([r['meanVy'] for r in rs])),
                          'meanYawRate': float(np.mean([r['meanYawRate'] for r in rs])),
                          'meanXyRmse': float(np.mean([r['xyRmse'] for r in rs])),
                          'meanYawRmse': float(np.mean([r['yawRmse'] for r in rs])),
                          'gateStatus': 'MET' if passed / len(rs) >= GATE['minTrialPassFraction'] else 'NOT_MET'})
        total_pass = sum(1 for r in trials if r['pass'])
        payload = {'schema': 'mb-robot-bench-v1', 'status': 'ok', 'design': design,
                   'body': {'native_sha256': native_digest(body_ir),
                            'mjcf': str(xml), 'mass_total_kg': float(sum(
                                float(b.get('mass', 0.0)) for b in body_ir.get('bodies', []))),
                            'nq': int(model.nq), 'nv': int(model.nv), 'nu': int(model.nu),
                            'policy_obs_dim': 61,
                            'policy_suitability': body_ir.get('controller', {}).get('status')},
                   'checkpoint': {'path': str(a.checkpoint)},
                   'protocol': {'seeds': list(SEEDS), 'worldsPerCase': WORLDS,
                                'cases': [{'name': c['name'], 'command': list(c['command'])} for c in CASES],
                                'durationSeconds': DURATION_S, 'metricWarmupSeconds': WARMUP_S,
                                'spawnZUsed': SPAWN_Z_BASE + ext},
                   'trials': trials, 'cases': cases,
                   'gateStatus': 'MET' if total_pass / len(trials) >= GATE['minTrialPassFraction'] else 'NOT_MET',
                   'seconds': round(time.monotonic() - t0, 1)}
    except Exception as e:
        payload = {'schema': 'mb-robot-bench-v1', 'status': 'error',
                   'error_type': type(e).__name__, 'message': str(e)[:500],
                   'seconds': round(time.monotonic() - t0, 1)}
    text = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text)
    print(text)
    sys.exit(0 if payload['status'] == 'ok' else 1)


if __name__ == '__main__':
    main()
