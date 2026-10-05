"""
Pure analysis-plan builders, shared by the legacy Streamlit app and the new
FastAPI/React dashboard. No streamlit imports here — safe for any host.
"""


def build_action_plan(mtf, setup):
    """Overall multi-timeframe action plan (aggregated across HTF/MID/STF)."""
    plan = {"bias": "NEUTRAL", "series": {}, "steps": [], "conflicts": [], "confluence": []}
    if not mtf or not mtf.get("results"):
        plan["steps"].append("Không có dữ liệu đa khung — chạy phân tích để xem phương án.")
        return plan

    cons = mtf.get("consensus", {})
    results = mtf.get("results", {})
    bias = cons.get("direction", "NEUTRAL")
    strength = cons.get("strength", 0.0)
    aligned = cons.get("aligned", 0)
    total = cons.get("total", 0)
    plan["bias"] = bias

    groups = {"HTF": ["1W", "1D", "4H"], "MID": ["1H", "30m"], "STF": ["15m", "5m", "1m"]}
    for g, tfs in groups.items():
        votes = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0}
        for tf in tfs:
            r = results.get(tf)
            if r and r.get("trend"):
                votes[r["trend"]["direction"]] = votes.get(r["trend"]["direction"], 0) + 1
        plan["series"][g] = max(votes, key=votes.get) if sum(votes.values()) else "NEUTRAL"

    if total == 0:
        plan["steps"].append("Không tải được dữ liệu đa khung — giữ thận trọng, xem lại nguồn dữ liệu.")
    elif bias == "NEUTRAL":
        plan["steps"].append(f"Chưa có xu hướng rõ ràng (mạnh {strength:.0%}, {aligned}/{total} khung đồng thuận).")
        plan["steps"].append("Phương án: đứng ngoài / giảm lot, chờ breakout khung lớn hoặc giá thoát vùng tích lũy.")
        plan["steps"].append("Nếu đang giữ lệnh: siết SL về vùng break-even.")
    elif strength >= 0.5 and aligned >= max(1, total - 1):
        plan["steps"].append(f"ĐỒNG THUẬN TOÀN KHUNG: {bias} — {aligned}/{total} khung.")
        plan["steps"].append(f"Phương án: ưu tiên vào {bias} theo xu hướng mạnh, không bắt đáy/đỉnh ngược hướng.")
        plan["steps"].append("Vào lệnh khi giá hồi về vùng hỗ trợ/kháng cự gần (xem Trade Plan), chia lot đúng rủi ro.")
    elif bias in ("LONG", "SHORT") and strength >= 0.3:
        dirs_ok = plan["series"].get("HTF") == bias or plan["series"].get("MID") == bias
        if dirs_ok:
            plan["steps"].append(f"Xu hướng {bias} ổn định ({strength:.0%}, {aligned}/{total} khung). Giao dịch cùng hướng, chờ điểm vào chuẩn.")
            plan["steps"].append("Ưu tiên hồi về vùng entry của Trade Plan; cắt lỗ nếu mất cấu trúc khung HTF.")
        else:
            plan["steps"].append(f"Xu hướng {bias} nhưng khung lớn chưa ủng hộ hoàn toàn — hạn chế vào lệnh, chỉ giao dịch ngắn hạn.")
    else:
        plan["steps"].append("Xu hướng yếu/trái chiều — kiên nhẫn chờ tín hiệu rõ ràng hơn.")

    if bias != "NEUTRAL":
        hdir = plan["series"].get("HTF")
        mdir = plan["series"].get("MID")
        sdir = plan["series"].get("STF")
        if hdir == bias and mdir == bias and sdir == bias:
            plan["confluence"].append("HTF-MID-STF cùng hướng — xác suất cao nhất.")
        elif hdir == bias and mdir == bias:
            plan["confluence"].append("HTF + MID cùng hướng — tín hiệu mạnh, chờ khung ngắn xác nhận entry.")
        elif hdir == bias:
            plan["confluence"].append("Khung lớn ủng hộ nhưng khung ngắn chưa theo — chờ đảo chiều STF.")
        if mdir != "NEUTRAL" and mdir != bias:
            plan["conflicts"].append(f"Mâu thuẫn HTF {hdir} vs MID {mdir} — ưu tiên khung lớn, giảm lot.")
        if sdir != "NEUTRAL" and sdir != bias:
            plan["conflicts"].append(f"Khung ngắn {sdir} ngược xu hướng chính {bias} — chờ tín hiệu ngược dòng STF.")

    bk = cons.get("active_breakouts", [])
    if bk:
        for b in bk[:3]:
            plan["confluence"].append(
                f"Breakout {b.get('tf')}: {b.get('detail')} @ {b.get('level')} ({int(b.get('confidence', 0) * 100)}%).")

    if not plan["confluence"] and not plan["conflicts"]:
        plan["confluence"].append("Chưa có tín hiệu nổi bật — chờ giá vào vùng quyết định.")
    return plan


def build_tf_action(direction: str, bk_type: str, bk: dict, near_sup, near_res) -> str:
    sup = f"≈ {near_sup:,.2f}" if near_sup else "chưa rõ"
    res = f"≈ {near_res:,.2f}" if near_res else "chưa rõ"
    if bk_type:
        lvl = f"{bk.get('level'):,.2f}" if bk.get("level") else "vùng phá vỡ"
        if bk_type == "BREAKOUT":
            return f"Đã phá vỡ phía TRÊN ({lvl}) — không đuổi; ưu tiên mua khi giá hồi và giữ trên vùng này."
        return f"Đã phá vỡ phía DƯỚI ({lvl}) — không đuổi; ưu tiên bán khi giá hồi và chặn tại vùng này."
    if direction == "LONG":
        return f"Mua hồi về S {sup}; cắt lỗ nếu mất S."
    if direction == "SHORT":
        return f"Bán hồi lên R {res}; cắt lỗ nếu phá R."
    return f"Chưa rõ hướng khung này — đứng ngoài, chờ breakout rõ."


def build_per_tf_plans(mtf):
    """Per-timeframe plan cards (no extra fetches, derived from MTF results)."""
    plans = []
    if not mtf or not mtf.get("results"):
        return plans
    for tf in mtf.get("timeframes", []):
        res = mtf["results"].get(tf)
        if not res:
            continue
        trend = res.get("trend", {}) or {}
        direction = trend.get("direction", "NEUTRAL")
        conf = float(trend.get("confidence", 0) or 0)
        score = int(trend.get("score", 0) or 0)
        reasons = list((trend.get("reasons") or [])[:4])
        bk = res.get("breakout", {}) or {}
        bk_type = bk.get("type") if bk.get("type") not in (None, "", "none") else None
        last = res.get("last_close")
        sr = (res.get("structure", {}) or {}).get("support_resistance", []) or []
        near_sup = near_res = None
        if last:
            for s in sr:
                p = s.get("price")
                if p is None:
                    continue
                if s.get("type") == "support" and p < last:
                    if near_sup is None or p > near_sup:
                        near_sup = p
                if s.get("type") == "resistance" and p > last:
                    if near_res is None or p < near_res:
                        near_res = p
        if last is None:
            near_sup = near_res = None
        action = build_tf_action(direction, bk_type, bk, near_sup, near_res)

        # Per-TF entry / SL / TP
        entry = sl = tp1 = tp2 = None
        if last and direction == "LONG" and near_sup:
            entry = near_sup
            sl = near_sup * 0.985  # 1.5% below support
            if near_res:
                tp1 = near_res
                tp2 = near_res + (near_res - sl) * 0.5  # 1.5R extension
        elif last and direction == "SHORT" and near_res:
            entry = near_res
            sl = near_res * 1.015  # 1.5% above resistance
            if near_sup:
                tp1 = near_sup
                tp2 = near_sup - (sl - near_sup) * 0.5  # 1.5R extension
        elif last and direction == "LONG" and near_res:
            # No support found, use breakout entry
            entry = near_res
            sl = last * 0.98
            tp1 = near_res + (near_res - sl) * 2
            tp2 = near_res + (near_res - sl) * 3
        elif last and direction == "SHORT" and near_sup:
            entry = near_sup
            sl = last * 1.02
            tp1 = near_sup - (sl - near_sup) * 2
            tp2 = near_sup - (sl - near_sup) * 3

        # Risk/reward
        rr = None
        if entry and sl and tp1:
            risk = abs(entry - sl)
            reward = abs(tp1 - entry)
            if risk > 0:
                rr = round(reward / risk, 2)

        plans.append({
            "tf": tf,
            "direction": direction,
            "confidence": conf,
            "score": score,
            "reasons": reasons,
            "breakout_type": bk_type,
            "breakout_detail": bk.get("detail", "") if bk else "",
            "support": near_sup,
            "resistance": near_res,
            "last_close": last,
            "bars": res.get("bars", 0),
            "action": action,
            "entry": round(entry, 6) if entry else None,
            "stop_loss": round(sl, 6) if sl else None,
            "take_profit_1": round(tp1, 6) if tp1 else None,
            "take_profit_2": round(tp2, 6) if tp2 else None,
            "risk_reward": rr,
        })
    return plans