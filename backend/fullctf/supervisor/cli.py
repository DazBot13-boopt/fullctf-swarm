"""CLI Supervisor / Mission Control : lire l'état d'un run + envoyer des ordres.

Usage (pendant qu'un run work-stealing tourne, même dans un autre terminal/tmux) :
  python -m fullctf.supervisor.cli <data_root> status      # qui bosse sur quoi
  python -m fullctf.supervisor.cli <data_root> pause|resume|stop
  python -m fullctf.supervisor.cli <data_root> debate <id> # forcer le débat

<data_root> = le même --data-root que le run.
"""

from __future__ import annotations

import argparse

from .mission_control import MissionControl


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Supervision d'un run FullCTF (Mission Control).")
    p.add_argument("data_root", help="le même --data-root que le run")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="état du run (qui bosse sur quoi)")
    sub.add_parser("pause", help="met le run en pause (entre deux étapes)")
    sub.add_parser("resume", help="reprend le run")
    sub.add_parser("stop", help="arrête le run proprement")
    d = sub.add_parser("debate", help="forcer un débat sur un challenge")
    d.add_argument("id", type=int)
    args = p.parse_args(argv)

    mc = MissionControl(args.data_root)
    if args.cmd == "status":
        st = mc.read_status()
        if not st:
            print("(pas encore d'état publié — le run a-t-il démarré ?)")
            return 0
        print(f"Agents : {', '.join(st.get('agents', []))}  |  "
              f"{st.get('solved', 0)}/{st.get('total', 0)} résolus")
        for c in st.get("challenges", []):
            on = f"  ← {', '.join(c['agents_on'])}" if c.get("agents_on") else ""
            win = f"  (gagnant: {c['winner']})" if c.get("winner") else ""
            flag = f"  flag={c['flag']}" if c.get("flag") else ""
            deb = f"  [{c['debate']}]" if c.get("debate") else ""
            print(f"  [{c['status']:9}] {c['category']}/{c['name']} (id={c['id']}){on}{win}{flag}{deb}")
    elif args.cmd == "pause":
        mc.set_order(paused=True); print("⏸  pause demandée (s'applique entre deux étapes)")
    elif args.cmd == "resume":
        mc.set_order(paused=False); print("▶  reprise demandée")
    elif args.cmd == "stop":
        mc.set_order(stopped=True); print("■  arrêt demandé (le run s'arrête proprement)")
    elif args.cmd == "debate":
        mc.add_force_debate(args.id); print(f"💬  débat forcé sur le challenge {args.id}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
