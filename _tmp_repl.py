import time
from collections import Counter
from realtime import RealtimeEngine

eng = RealtimeEngine()
eng.start()
time.sleep(15)
snap = {q["sym"]: (q["src"], q["price"], q.get("chg")) for q in eng.snapshot()}
print("quotes:", len(snap))
print(Counter(v[0] for v in snap.values()))
print()
for s in ["OANDA:XAUUSD", "TVC:XAUUSD", "COMEX:GC1!", "OANDA:XAGUSD",
          "NYMEX:CL1!", "ICE:BZ1!", "TVC:SPX", "TVC:NDX", "TVC:DJI",
          "TVC:DXY", "TVC:VIX", "TVC:HSI"]:
    print(s, snap.get(s))
eng.stop()
