
    cached = load_data()
    cached["trend"]         = payload.get("trend", [])
    cached["månadsLabels"]  = payload.get("månadsLabels", [])
    cached["trend_synkad"]  = datetime.now().isoformat()
    save_data(cached)
    return jsonify({"ok": True})


# ── Route: API – spelardata (för planeringsverktyget) ─────────────────────────


@app.route("/api/spelare")
def api_spelare():
    """Returnerar alla spelares nuvarande matchantal + planerade."""
    if "inloggad" not in session:
        return jsonify([]), 401
    cached   = load_data()
    planning = load_planning()


    # Räkna planerade matcher per spelare per serie
    planerade = defaultdict(lambda: defaultdict(int))
    for mid, mdata in planning["matcher"].items():
        sid = mdata.get("serie_id","")
        for namn in mdata.get("spelare",[]):
            planerade[namn][sid] += 1


    narvaro  = cached.get("narvaro", {})
    spelare  = cached.get("spelare", [])


    fogis_spl = cached.get("fogis_spelare", [])


    alla = slå_ihop_spelare(fogis_spl, narvaro, spelare)
    for sp in alla:
        sp["planerade_serier"] = dict(planerade.get(sp["namn"], {}))
        sp["planerade_totalt"] = sum(sp["planerade_serier"].values())


    return jsonify(alla)


# ── Route: Fogis-cache (spara vid dashboard-laddning) ─────────────────────────


@app.route("/sync/fogis", methods=["POST"])
def sync_fogis():
    """Cachelagrar Fogis spelarlistan."""
    if "inloggad" not in session:
        return jsonify({"ok": False}), 401
    payload = request.get_json()
    cached  = load_data()
    cached["fogis_spelare"] = payload.get("spelare", [])
    save_data(cached)
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

