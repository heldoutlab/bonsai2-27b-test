# -*- coding: utf-8 -*-
"""Mock tool environments + multi-step tool-calling tasks (bonsai2 test set).

Stdlib only; runs on Python 3.9 and 3.12.  Tasks are graded on the FINAL STATE
of the mock environment (task["check"](env.state)).

Layout
  ENVS   name -> environment class (TOOLS in OpenAI chat-completions format,
         __init__(init), call(name, args) which never raises)
  TASKS  T01..T40 (test set, 8 per environment) then TP1..TP3 (pilot)

Run this file directly to self-verify:  prints "OK 43/43".
"""
import copy
import datetime
import itertools
import json
import random
import re


# --------------------------------------------------------------------------
# shared plumbing
# --------------------------------------------------------------------------
class _Rule(Exception):
    """A business-rule / lookup failure; turned into {"error": ...}."""


def _norm(schema, v, path):
    """Validate v against a (small subset of) JSON Schema. Returns (value, err)."""
    t = schema.get("type")
    types = t if isinstance(t, list) else [t]
    if v is None:
        if "null" in types:
            return None, None
        return None, "'%s' must not be null" % path
    base = [x for x in types if x != "null"][0]
    if base == "string":
        if not isinstance(v, str):
            return None, "'%s' must be a string" % path
        if "enum" in schema and v not in schema["enum"]:
            return None, "'%s' must be one of: %s" % (path, ", ".join(schema["enum"]))
        return v, None
    if base == "integer":
        if isinstance(v, bool):
            return None, "'%s' must be an integer" % path
        if isinstance(v, float):
            if v != v or v in (float("inf"), float("-inf")) or v != int(v):
                return None, "'%s' must be an integer" % path
            v = int(v)
        if not isinstance(v, int):
            return None, "'%s' must be an integer" % path
        if "minimum" in schema and v < schema["minimum"]:
            return None, "'%s' must be >= %d" % (path, schema["minimum"])
        return v, None
    if base == "boolean":
        if not isinstance(v, bool):
            return None, "'%s' must be true or false" % path
        return v, None
    if base == "array":
        if not isinstance(v, list):
            return None, "'%s' must be an array" % path
        if len(v) < schema.get("minItems", 0):
            return None, "'%s' must contain at least %d item(s)" % (path, schema["minItems"])
        out = []
        for n, item in enumerate(v):
            val, err = _norm(schema["items"], item, "%s[%d]" % (path, n))
            if err:
                return None, err
            out.append(val)
        return out, None
    if base == "object":
        if not isinstance(v, dict):
            return None, "'%s' must be an object" % path
        props = schema.get("properties", {})
        required = schema.get("required", [])
        pre = "" if path == "arguments" else path + "."
        out = {}
        for k in v:
            if not isinstance(k, str) or k not in props:
                return None, "unexpected argument '%s%s' (allowed: %s)" % (
                    pre, k, ", ".join(sorted(props)) or "none")
        for k in required:
            if k not in v:
                return None, "missing required argument '%s%s'" % (pre, k)
        for k, val in v.items():
            ptypes = props[k].get("type")
            ptypes = ptypes if isinstance(ptypes, list) else [ptypes]
            if val is None and k not in required and "null" not in ptypes:
                continue  # optional argument sent as null == omitted
            val, err = _norm(props[k], val, pre + k)
            if err:
                return None, err
            out[k] = val
        return out, None
    return None, "'%s' has an unsupported type" % path


def _fn(name, desc, props=None, required=()):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props or {},
                       "required": list(required), "additionalProperties": False}}}


def _s(desc, enum=None):
    d = {"type": "string", "description": desc}
    if enum:
        d["enum"] = list(enum)
    return d


def _i(desc, minimum=None):
    d = {"type": "integer", "description": desc}
    if minimum is not None:
        d["minimum"] = minimum
    return d


def _arr(desc, items, min_items=0):
    d = {"type": "array", "description": desc, "items": items}
    if min_items:
        d["minItems"] = min_items
    return d


def _pdate(s, what="date"):
    if not isinstance(s, str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        raise _Rule("%s must be formatted YYYY-MM-DD, got '%s'" % (what, s))
    try:
        return datetime.date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    except ValueError:
        raise _Rule("%s '%s' is not a real calendar date" % (what, s))


def _ptime(s, what="time"):
    if not isinstance(s, str) or not re.match(r"^\d{2}:\d{2}$", s):
        raise _Rule("%s must be formatted HH:MM (24h), got '%s'" % (what, s))
    h, m = int(s[0:2]), int(s[3:5])
    if h > 23 or m > 59:
        raise _Rule("%s '%s' is not a valid time" % (what, s))
    return h * 60 + m


def _hm(minutes):
    return "%02d:%02d" % (minutes // 60, minutes % 60)


_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_DAYNAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class _Env(object):
    TOOLS = []

    def __init__(self, init):
        self.state = copy.deepcopy(init)

    def _restore(self, snap):
        self.state.clear()
        self.state.update(snap)

    def call(self, name, args):
        try:
            return self._call(name, args)
        except Exception as e:  # never raise
            return {"error": "invalid call (%s)" % type(e).__name__}

    def _call(self, name, args):
        if not isinstance(name, str):
            return {"error": "tool name must be a string"}
        spec = None
        for t in self.TOOLS:
            if t["function"]["name"] == name:
                spec = t["function"]
        if spec is None:
            return {"error": "unknown tool '%s'; available tools: %s" % (
                name[:60], ", ".join(t["function"]["name"] for t in self.TOOLS))}
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return {"error": "arguments must be a JSON object"}
        args, err = _norm(spec["parameters"], args, "arguments")
        if err:
            return {"error": err}
        snap = copy.deepcopy(self.state)
        try:
            res = getattr(self, "_t_" + name)(args)
            res = json.loads(json.dumps(res))
        except _Rule as e:
            self._restore(snap)
            return {"error": str(e)}
        except Exception as e:
            self._restore(snap)
            return {"error": "internal error (%s); nothing was changed" % type(e).__name__}
        return res


# --------------------------------------------------------------------------
# 1. warehouse inventory + purchase orders
# --------------------------------------------------------------------------
class InventoryEnv(_Env):
    TOOLS = [
        _fn("get_warehouse_info",
            "Today's date, the stock locations and the list of suppliers (with each supplier's minimum quantity per order line)."),
        _fn("list_items",
            "List items (sku, name, supplier, total on hand over all locations). Optional filters.",
            {"query": _s("Case-insensitive text that must appear in the item name or SKU."),
             "supplier_id": _s("Only items bought from this supplier, e.g. SUP-01.")}),
        _fn("get_item",
            "Full record for one item: stock per location, reorder point, pack size, supplier, flags.",
            {"sku": _s("Item SKU.")}, ["sku"]),
        _fn("list_purchase_orders",
            "List purchase orders with their lines.",
            {"status": _s("Only orders in this status.", ["open", "cancelled"])}),
        _fn("create_purchase_order",
            "Create a new open purchase order to one supplier. Every line must be an item of that supplier, "
            "at least the supplier's minimum line quantity, and a whole number of packs.",
            {"supplier_id": _s("Supplier to order from."),
             "lines": _arr("Order lines.", {
                 "type": "object",
                 "properties": {"sku": _s("Item SKU."), "qty": _i("Units to order.", 1)},
                 "required": ["sku", "qty"], "additionalProperties": False}, 1),
             "expected_date": _s("Optional expected delivery date, YYYY-MM-DD.")},
            ["supplier_id", "lines"]),
        _fn("set_po_line",
            "Set the quantity of one SKU on an open purchase order. Adds the line if the SKU is not on the order yet; "
            "qty 0 removes the line.",
            {"po_id": _s("Purchase order id, e.g. PO-1001."), "sku": _s("Item SKU."),
             "qty": _i("New quantity for the line (0 removes it).", 0)},
            ["po_id", "sku", "qty"]),
        _fn("cancel_purchase_order",
            "Cancel an open purchase order.",
            {"po_id": _s("Purchase order id."),
             "reason": _s("Why it is cancelled.", ["supplier_delay", "duplicate", "no_longer_needed", "other"])},
            ["po_id", "reason"]),
        _fn("transfer_stock",
            "Move units of an item from one location to another.",
            {"sku": _s("Item SKU."), "from_location": _s("Source location code."),
             "to_location": _s("Destination location code."), "qty": _i("Units to move.", 1)},
            ["sku", "from_location", "to_location", "qty"]),
        _fn("adjust_stock",
            "Add to or subtract from the stock of an item at one location (write-offs, count corrections).",
            {"sku": _s("Item SKU."), "location": _s("Location code."),
             "delta": _i("Change in units; negative to reduce stock."),
             "reason": _s("Reason code.", ["damaged", "expired", "count_correction", "found"])},
            ["sku", "location", "delta", "reason"]),
        _fn("set_item_flag",
            "Set or clear a flag on an item.",
            {"sku": _s("Item SKU."), "flag": _s("Which flag.", ["reviewed", "hold", "discontinued"]),
             "value": {"type": "boolean", "description": "true to set, false to clear."}},
            ["sku", "flag", "value"]),
    ]

    def _item(self, sku):
        it = self.state["items"].get(sku)
        if it is None:
            raise _Rule("unknown SKU '%s'" % sku)
        return it

    def _po(self, po_id):
        po = self.state["purchase_orders"].get(po_id)
        if po is None:
            raise _Rule("unknown purchase order '%s'" % po_id)
        return po

    def _loc(self, loc):
        if loc not in self.state["locations"]:
            raise _Rule("unknown location '%s' (locations: %s)" % (loc, ", ".join(self.state["locations"])))

    def _open_po_with(self, sku, exclude=None):
        for pid in sorted(self.state["purchase_orders"]):
            po = self.state["purchase_orders"][pid]
            if pid != exclude and po["status"] == "open" and sku in po["lines"]:
                return pid
        return None

    def _po_view(self, pid):
        po = self.state["purchase_orders"][pid]
        return {"po_id": pid, "supplier_id": po["supplier"], "created": po["created"],
                "expected_date": po["expected"], "status": po["status"],
                "cancel_reason": po["cancel_reason"],
                "lines": [{"sku": k, "qty": po["lines"][k]} for k in sorted(po["lines"])]}

    def _check_line(self, po_id, supplier_id, sku, qty, adding):
        it = self._item(sku)
        sup = self.state["suppliers"][supplier_id]
        if it["flags"]["discontinued"]:
            raise _Rule("%s is discontinued and cannot be ordered" % sku)
        if it["supplier"] != supplier_id:
            raise _Rule("%s is supplied by %s, not by %s" % (sku, it["supplier"], supplier_id))
        if qty < sup["min_line_qty"]:
            raise _Rule("line for %s: qty %d is below the minimum line quantity of %d for %s" % (
                sku, qty, sup["min_line_qty"], supplier_id))
        if qty % it["pack_size"] != 0:
            raise _Rule("line for %s: qty %d is not a multiple of the pack size %d" % (sku, qty, it["pack_size"]))
        if adding:
            other = self._open_po_with(sku, po_id)
            if other:
                raise _Rule("%s is already on open purchase order %s; an item may be on only one open order - "
                            "change that order (or cancel it first)" % (sku, other))

    def _t_get_warehouse_info(self, a):
        st = self.state
        return {"today": st["today"], "locations": list(st["locations"]),
                "suppliers": [{"supplier_id": k, "name": v["name"], "min_line_qty": v["min_line_qty"],
                               "active": v["active"]} for k, v in sorted(st["suppliers"].items())]}

    def _t_list_items(self, a):
        q = a.get("query", "").strip().lower()
        sup = a.get("supplier_id")
        if sup is not None and sup not in self.state["suppliers"]:
            raise _Rule("unknown supplier '%s'" % sup)
        out = []
        for sku, it in sorted(self.state["items"].items()):
            if q and q not in it["name"].lower() and q not in sku.lower():
                continue
            if sup is not None and it["supplier"] != sup:
                continue
            out.append({"sku": sku, "name": it["name"], "supplier_id": it["supplier"],
                        "total_on_hand": sum(it["stock"].values()),
                        "discontinued": it["flags"]["discontinued"]})
        return {"items": out}

    def _t_get_item(self, a):
        it = self._item(a["sku"])
        return {"sku": a["sku"], "name": it["name"], "supplier_id": it["supplier"],
                "pack_size": it["pack_size"], "reorder_point": it["reorder_point"],
                "stock": dict(it["stock"]), "total_on_hand": sum(it["stock"].values()),
                "flags": dict(it["flags"]), "on_open_purchase_order": self._open_po_with(a["sku"])}

    def _t_list_purchase_orders(self, a):
        return {"purchase_orders": [self._po_view(p) for p in sorted(self.state["purchase_orders"])
                                    if a.get("status") in (None, self.state["purchase_orders"][p]["status"])]}

    def _t_create_purchase_order(self, a):
        st = self.state
        sup = st["suppliers"].get(a["supplier_id"])
        if sup is None:
            raise _Rule("unknown supplier '%s'" % a["supplier_id"])
        if not sup["active"]:
            raise _Rule("supplier %s is inactive" % a["supplier_id"])
        expected = a.get("expected_date")
        if expected is not None:
            _pdate(expected, "expected_date")
            if expected < st["today"]:
                raise _Rule("expected_date is before today (%s)" % st["today"])
        lines = {}
        for ln in a["lines"]:
            if ln["sku"] in lines:
                raise _Rule("SKU %s appears on more than one line" % ln["sku"])
            self._check_line(None, a["supplier_id"], ln["sku"], ln["qty"], True)
            lines[ln["sku"]] = ln["qty"]
        pid = "PO-%d" % st["next_po"]
        st["next_po"] += 1
        st["purchase_orders"][pid] = {"supplier": a["supplier_id"], "created": st["today"],
                                      "expected": expected, "status": "open",
                                      "cancel_reason": None, "lines": lines}
        return {"created": self._po_view(pid)}

    def _t_set_po_line(self, a):
        po = self._po(a["po_id"])
        if po["status"] != "open":
            raise _Rule("%s is %s; only open orders can be changed" % (a["po_id"], po["status"]))
        sku, qty = a["sku"], a["qty"]
        self._item(sku)
        if qty == 0:
            if sku not in po["lines"]:
                raise _Rule("%s has no line for %s" % (a["po_id"], sku))
            if len(po["lines"]) == 1:
                raise _Rule("cannot remove the last line of %s; cancel the order instead" % a["po_id"])
            del po["lines"][sku]
        else:
            self._check_line(a["po_id"], po["supplier"], sku, qty, sku not in po["lines"])
            po["lines"][sku] = qty
        return {"updated": self._po_view(a["po_id"])}

    def _t_cancel_purchase_order(self, a):
        po = self._po(a["po_id"])
        if po["status"] != "open":
            raise _Rule("%s is already %s" % (a["po_id"], po["status"]))
        po["status"] = "cancelled"
        po["cancel_reason"] = a["reason"]
        return {"cancelled": self._po_view(a["po_id"])}

    def _t_transfer_stock(self, a):
        it = self._item(a["sku"])
        self._loc(a["from_location"])
        self._loc(a["to_location"])
        if a["from_location"] == a["to_location"]:
            raise _Rule("from_location and to_location are the same")
        have = it["stock"].get(a["from_location"], 0)
        if a["qty"] > have:
            raise _Rule("only %d of %s at %s; cannot move %d" % (have, a["sku"], a["from_location"], a["qty"]))
        it["stock"][a["from_location"]] = have - a["qty"]
        it["stock"][a["to_location"]] = it["stock"].get(a["to_location"], 0) + a["qty"]
        return {"sku": a["sku"], "stock": dict(it["stock"])}

    def _t_adjust_stock(self, a):
        it = self._item(a["sku"])
        self._loc(a["location"])
        if a["delta"] == 0:
            raise _Rule("delta must not be 0")
        have = it["stock"].get(a["location"], 0)
        if have + a["delta"] < 0:
            raise _Rule("only %d of %s at %s; stock cannot go negative" % (have, a["sku"], a["location"]))
        it["stock"][a["location"]] = have + a["delta"]
        self.state["adjustments"].append({"sku": a["sku"], "location": a["location"],
                                          "delta": a["delta"], "reason": a["reason"]})
        return {"sku": a["sku"], "stock": dict(it["stock"])}

    def _t_set_item_flag(self, a):
        it = self._item(a["sku"])
        if a["flag"] == "discontinued" and a["value"]:
            total = sum(it["stock"].values())
            if total > 0:
                raise _Rule("cannot discontinue %s while %d units are still in stock" % (a["sku"], total))
            po = self._open_po_with(a["sku"])
            if po:
                raise _Rule("cannot discontinue %s while it is on open purchase order %s" % (a["sku"], po))
        it["flags"][a["flag"]] = a["value"]
        return {"sku": a["sku"], "flags": dict(it["flags"])}


# --------------------------------------------------------------------------
# 2. shared calendar with rooms
# --------------------------------------------------------------------------
_EV_CHANGES = {
    "type": "object",
    "description": "Fields to change; omit the ones that stay the same.",
    "properties": {
        "title": _s("New title."),
        "date": _s("New date, YYYY-MM-DD."),
        "start": _s("New start time, HH:MM."),
        "end": _s("New end time, HH:MM."),
        "room_id": {"type": ["string", "null"], "description": "New room id, or null for no room."}},
    "additionalProperties": False}


class CalendarEnv(_Env):
    TOOLS = [
        _fn("get_calendar_info", "Today's date and weekday, and the office hours within which meetings may be booked."),
        _fn("find_people", "Look up people by (part of) their name. Returns ids, names and teams.",
            {"query": _s("Case-insensitive part of a name.")}, ["query"]),
        _fn("list_rooms", "List meeting rooms with capacity and features. Does not show availability.",
            {"min_capacity": _i("Only rooms with at least this capacity.", 1),
             "feature": _s("Only rooms with this feature.", ["video", "whiteboard", "projector"])}),
        _fn("list_events", "List the meetings on one date, optionally only those of one person or in one room.",
            {"date": _s("Date, YYYY-MM-DD."), "person_id": _s("Only meetings this person attends."),
             "room_id": _s("Only meetings in this room.")}, ["date"]),
        _fn("get_event", "Full details of one meeting.", {"event_id": _s("Meeting id, e.g. E101.")}, ["event_id"]),
        _fn("create_event",
            "Create a meeting. The organiser is always an attendee. Fails if the room is occupied or too small, "
            "or if any attendee already has an overlapping meeting.",
            {"title": _s("Meeting title."), "date": _s("Date, YYYY-MM-DD."),
             "start": _s("Start time HH:MM (15-minute steps)."), "end": _s("End time HH:MM (15-minute steps)."),
             "organizer_id": _s("Person id of the organiser."),
             "attendee_ids": _arr("Person ids of the other attendees.", {"type": "string"}),
             "room_id": {"type": ["string", "null"], "description": "Room id, or null/omitted for no room."}},
            ["title", "date", "start", "end", "organizer_id"]),
        _fn("update_event",
            "Change the title, date, time and/or room of a meeting. Same rules as create_event.",
            {"event_id": _s("Meeting id."), "changes": _EV_CHANGES}, ["event_id", "changes"]),
        _fn("set_attendees",
            "Add and/or remove attendees of a meeting. The organiser cannot be removed.",
            {"event_id": _s("Meeting id."),
             "add": _arr("Person ids to add.", {"type": "string"}),
             "remove": _arr("Person ids to remove.", {"type": "string"})}, ["event_id"]),
        _fn("cancel_event", "Cancel a meeting; it is removed from the calendar.",
            {"event_id": _s("Meeting id.")}, ["event_id"]),
    ]

    def _ev(self, eid):
        ev = self.state["events"].get(eid)
        if ev is None:
            raise _Rule("unknown meeting '%s'" % eid)
        return ev

    def _person(self, pid):
        if pid not in self.state["people"]:
            raise _Rule("unknown person '%s'" % pid)
        return self.state["people"][pid]

    def _room(self, rid):
        if rid not in self.state["rooms"]:
            raise _Rule("unknown room '%s'" % rid)
        return self.state["rooms"][rid]

    def _view(self, eid):
        ev = self.state["events"][eid]
        return {"event_id": eid, "title": ev["title"], "date": ev["date"], "start": ev["start"],
                "end": ev["end"], "room_id": ev["room"], "organizer_id": ev["organizer"],
                "attendee_ids": list(ev["attendees"])}

    def _validate(self, ev, eid):
        st = self.state
        if not ev["title"].strip():
            raise _Rule("title must not be empty")
        d = _pdate(ev["date"])
        if ev["date"] < st["today"]:
            raise _Rule("%s is in the past (today is %s)" % (ev["date"], st["today"]))
        if d.weekday() >= 5:
            raise _Rule("%s is a %s; meetings can only be on weekdays" % (ev["date"], _DAYNAMES[d.weekday()]))
        s, e = _ptime(ev["start"], "start"), _ptime(ev["end"], "end")
        if s >= e:
            raise _Rule("end must be after start")
        if s % 15 or e % 15:
            raise _Rule("times must be on 15-minute steps")
        if s < _ptime(st["hours"]["open"]) or e > _ptime(st["hours"]["close"]):
            raise _Rule("meetings must be within office hours %s-%s" % (st["hours"]["open"], st["hours"]["close"]))
        for p in ev["attendees"]:
            self._person(p)
        if ev["room"] is not None:
            room = self._room(ev["room"])
            if len(ev["attendees"]) > room["capacity"]:
                raise _Rule("room %s (%s) holds %d people but the meeting has %d attendees" % (
                    ev["room"], room["name"], room["capacity"], len(ev["attendees"])))
        for oid in sorted(st["events"]):
            o = st["events"][oid]
            if oid == eid or o["date"] != ev["date"]:
                continue
            if not (s < _ptime(o["end"]) and _ptime(o["start"]) < e):
                continue
            if ev["room"] is not None and o["room"] == ev["room"]:
                raise _Rule("room %s is occupied by %s '%s' (%s-%s)" % (
                    ev["room"], oid, o["title"], o["start"], o["end"]))
            for p in ev["attendees"]:
                if p in o["attendees"]:
                    raise _Rule("%s (%s) already has %s '%s' at %s-%s on %s" % (
                        p, st["people"][p]["name"], oid, o["title"], o["start"], o["end"], o["date"]))

    def _t_get_calendar_info(self, a):
        d = _pdate(self.state["today"])
        return {"today": self.state["today"], "weekday": _DAYNAMES[d.weekday()],
                "office_hours": dict(self.state["hours"]), "meeting_days": "Monday-Friday"}

    def _t_find_people(self, a):
        q = a["query"].strip().lower()
        return {"people": [{"person_id": k, "name": v["name"], "team": v["team"]}
                           for k, v in sorted(self.state["people"].items()) if q in v["name"].lower()]}

    def _t_list_rooms(self, a):
        out = []
        for k, v in sorted(self.state["rooms"].items()):
            if v["capacity"] < a.get("min_capacity", 0):
                continue
            if a.get("feature") and a["feature"] not in v["features"]:
                continue
            out.append({"room_id": k, "name": v["name"], "capacity": v["capacity"], "features": list(v["features"])})
        return {"rooms": out}

    def _t_list_events(self, a):
        _pdate(a["date"])
        if "person_id" in a:
            self._person(a["person_id"])
        if "room_id" in a:
            self._room(a["room_id"])
        ids = [k for k, v in self.state["events"].items()
               if v["date"] == a["date"]
               and ("person_id" not in a or a["person_id"] in v["attendees"])
               and ("room_id" not in a or a["room_id"] == v["room"])]
        ids.sort(key=lambda k: (self.state["events"][k]["start"], k))
        return {"date": a["date"], "events": [self._view(k) for k in ids]}

    def _t_get_event(self, a):
        self._ev(a["event_id"])
        return self._view(a["event_id"])

    def _t_create_event(self, a):
        st = self.state
        self._person(a["organizer_id"])
        ev = {"title": a["title"].strip(), "date": a["date"], "start": a["start"], "end": a["end"],
              "room": a.get("room_id"), "organizer": a["organizer_id"],
              "attendees": sorted(set(a.get("attendee_ids", [])) | set([a["organizer_id"]]))}
        self._validate(ev, None)
        eid = "E%d" % st["next_event"]
        st["next_event"] += 1
        st["events"][eid] = ev
        return {"created": self._view(eid)}

    def _t_update_event(self, a):
        ev = self._ev(a["event_id"])
        ch = a["changes"]
        if not ch:
            raise _Rule("changes is empty; give at least one field to change")
        for k in ("title", "date", "start", "end"):
            if k in ch:
                ev[k] = ch[k].strip() if k == "title" else ch[k]
        if "room_id" in ch:
            ev["room"] = ch["room_id"]
        self._validate(ev, a["event_id"])
        return {"updated": self._view(a["event_id"])}

    def _t_set_attendees(self, a):
        ev = self._ev(a["event_id"])
        add, rem = a.get("add", []), a.get("remove", [])
        if not add and not rem:
            raise _Rule("give at least one person to add or remove")
        cur = set(ev["attendees"])
        for p in rem:
            self._person(p)
            if p == ev["organizer"]:
                raise _Rule("%s is the organiser and cannot be removed" % p)
            if p not in cur:
                raise _Rule("%s is not an attendee of %s" % (p, a["event_id"]))
            cur.discard(p)
        for p in add:
            self._person(p)
            cur.add(p)
        ev["attendees"] = sorted(cur)
        self._validate(ev, a["event_id"])
        return {"updated": self._view(a["event_id"])}

    def _t_cancel_event(self, a):
        ev = self._ev(a["event_id"])
        if ev["date"] < self.state["today"]:
            raise _Rule("past meetings cannot be cancelled")
        del self.state["events"][a["event_id"]]
        return {"cancelled": a["event_id"]}


# --------------------------------------------------------------------------
# 3. ticket tracker
# --------------------------------------------------------------------------
_STATUSES = ["open", "in_progress", "blocked", "resolved", "closed"]
_PRIOS = ["low", "medium", "high", "urgent"]


class TicketEnv(_Env):
    TOOLS = [
        _fn("search_tickets",
            "Search tickets; all filters are optional and combined with AND. Returns summaries "
            "(no dependency lists - use get_ticket for those).",
            {"query": _s("Case-insensitive text that must appear in the title."),
             "status": _s("Only tickets in this status.", _STATUSES),
             "assignee_id": _s("Only tickets assigned to this user id."),
             "label": _s("Only tickets carrying this label."),
             "sprint_id": _s("Only tickets in this sprint.")}),
        _fn("get_ticket", "Full details of one ticket, including what it depends on.",
            {"ticket_id": _s("Ticket id, e.g. TK-201.")}, ["ticket_id"]),
        _fn("list_users", "All users with id, name, role and whether they are on leave."),
        _fn("list_sprints", "All sprints with state, capacity in points and points already committed."),
        _fn("create_ticket", "Create a ticket (status open, no sprint).",
            {"title": _s("Ticket title."), "priority": _s("Priority.", _PRIOS),
             "estimate": _i("Estimate in points.", 0),
             "labels": _arr("Labels to put on the ticket.", {"type": "string"}),
             "assignee_id": {"type": ["string", "null"], "description": "User id, or null/omitted for unassigned."},
             "depends_on": _arr("Ids of tickets this one depends on.", {"type": "string"})},
            ["title", "priority", "estimate"]),
        _fn("update_ticket", "Change basic fields of a ticket.",
            {"ticket_id": _s("Ticket id."),
             "fields": {"type": "object", "description": "Fields to change; omit the rest.",
                        "properties": {
                            "title": _s("New title."), "priority": _s("New priority.", _PRIOS),
                            "estimate": _i("New estimate in points.", 0),
                            "assignee_id": {"type": ["string", "null"],
                                            "description": "New assignee user id, or null to unassign."}},
                        "additionalProperties": False}},
            ["ticket_id", "fields"]),
        _fn("set_status",
            "Change a ticket's status. A ticket can only be resolved or closed when everything it depends on is "
            "resolved or closed, and can only be closed from resolved.",
            {"ticket_id": _s("Ticket id."), "status": _s("New status.", _STATUSES)}, ["ticket_id", "status"]),
        _fn("edit_labels", "Add and/or remove labels on a ticket.",
            {"ticket_id": _s("Ticket id."), "add": _arr("Labels to add.", {"type": "string"}),
             "remove": _arr("Labels to remove.", {"type": "string"})}, ["ticket_id"]),
        _fn("link_dependency", "Add or remove a 'ticket_id depends on depends_on_id' link.",
            {"ticket_id": _s("The ticket that is waiting."), "depends_on_id": _s("The ticket it waits for."),
             "action": _s("add or remove the link.", ["add", "remove"])},
            ["ticket_id", "depends_on_id", "action"]),
        _fn("move_to_sprint", "Put a ticket into a sprint, or take it out of any sprint.",
            {"ticket_id": _s("Ticket id."),
             "sprint_id": {"type": ["string", "null"], "description": "Sprint id, or null for no sprint (backlog)."}},
            ["ticket_id", "sprint_id"]),
    ]

    def _tk(self, tid):
        t = self.state["tickets"].get(tid)
        if t is None:
            raise _Rule("unknown ticket '%s'" % tid)
        return t

    def _user(self, uid, assign=False):
        u = self.state["users"].get(uid)
        if u is None:
            raise _Rule("unknown user '%s'" % uid)
        if assign and u["on_leave"]:
            raise _Rule("%s (%s) is on leave and cannot be assigned tickets" % (uid, u["name"]))
        return u

    def _labels_ok(self, labels):
        for lb in labels:
            if lb not in self.state["labels"]:
                raise _Rule("unknown label '%s' (labels: %s)" % (lb, ", ".join(self.state["labels"])))

    def _used(self, sid, skip=None):
        return sum(t["estimate"] for k, t in self.state["tickets"].items() if t["sprint"] == sid and k != skip)

    def _summary(self, tid):
        t = self.state["tickets"][tid]
        return {"ticket_id": tid, "title": t["title"], "status": t["status"], "priority": t["priority"],
                "assignee_id": t["assignee"], "labels": list(t["labels"]), "estimate": t["estimate"],
                "sprint_id": t["sprint"]}

    def _full(self, tid):
        d = self._summary(tid)
        d["depends_on"] = list(self.state["tickets"][tid]["depends_on"])
        return d

    def _t_search_tickets(self, a):
        q = a.get("query", "").strip().lower()
        if "assignee_id" in a:
            self._user(a["assignee_id"])
        if "sprint_id" in a and a["sprint_id"] not in self.state["sprints"]:
            raise _Rule("unknown sprint '%s'" % a["sprint_id"])
        out = []
        for tid in sorted(self.state["tickets"]):
            t = self.state["tickets"][tid]
            if q and q not in t["title"].lower():
                continue
            if "status" in a and t["status"] != a["status"]:
                continue
            if "assignee_id" in a and t["assignee"] != a["assignee_id"]:
                continue
            if "label" in a and a["label"] not in t["labels"]:
                continue
            if "sprint_id" in a and t["sprint"] != a["sprint_id"]:
                continue
            out.append(self._summary(tid))
        return {"count": len(out), "tickets": out}

    def _t_get_ticket(self, a):
        self._tk(a["ticket_id"])
        return self._full(a["ticket_id"])

    def _t_list_users(self, a):
        return {"users": [{"user_id": k, "name": v["name"], "role": v["role"], "on_leave": v["on_leave"]}
                          for k, v in sorted(self.state["users"].items())]}

    def _t_list_sprints(self, a):
        return {"sprints": [{"sprint_id": k, "name": v["name"], "state": v["state"],
                             "capacity_points": v["capacity"], "committed_points": self._used(k)}
                            for k, v in sorted(self.state["sprints"].items())]}

    def _t_create_ticket(self, a):
        st = self.state
        if not a["title"].strip():
            raise _Rule("title must not be empty")
        labels = sorted(set(a.get("labels", [])))
        self._labels_ok(labels)
        if a.get("assignee_id") is not None:
            self._user(a["assignee_id"], True)
        deps = sorted(set(a.get("depends_on", [])))
        for d in deps:
            self._tk(d)
        tid = "TK-%d" % st["next_ticket"]
        st["next_ticket"] += 1
        st["tickets"][tid] = {"title": a["title"].strip(), "status": "open", "priority": a["priority"],
                              "assignee": a.get("assignee_id"), "labels": labels, "depends_on": deps,
                              "estimate": a["estimate"], "sprint": None}
        return {"created": self._full(tid)}

    def _t_update_ticket(self, a):
        t = self._tk(a["ticket_id"])
        f = a["fields"]
        if not f:
            raise _Rule("fields is empty; give at least one field to change")
        if "title" in f:
            if not f["title"].strip():
                raise _Rule("title must not be empty")
            t["title"] = f["title"].strip()
        if "priority" in f:
            t["priority"] = f["priority"]
        if "assignee_id" in f:
            if f["assignee_id"] is None:
                if t["status"] == "in_progress":
                    raise _Rule("an in_progress ticket must have an assignee")
            else:
                self._user(f["assignee_id"], True)
            t["assignee"] = f["assignee_id"]
        if "estimate" in f:
            if t["sprint"] is not None:
                sp = self.state["sprints"][t["sprint"]]
                if f["estimate"] > t["estimate"] and self._used(t["sprint"], a["ticket_id"]) + f["estimate"] > sp["capacity"]:
                    raise _Rule("estimate %d would exceed the capacity of %s" % (f["estimate"], t["sprint"]))
            t["estimate"] = f["estimate"]
        return {"updated": self._full(a["ticket_id"])}

    def _t_set_status(self, a):
        t = self._tk(a["ticket_id"])
        new = a["status"]
        if t["status"] == new:
            raise _Rule("%s is already %s" % (a["ticket_id"], new))
        if t["status"] == "closed":
            raise _Rule("%s is closed and cannot change status" % a["ticket_id"])
        if new in ("resolved", "closed"):
            pending = [d for d in t["depends_on"]
                       if self.state["tickets"][d]["status"] not in ("resolved", "closed")]
            if pending:
                raise _Rule("%s depends on unfinished ticket(s): %s" % (a["ticket_id"], ", ".join(
                    "%s (%s)" % (d, self.state["tickets"][d]["status"]) for d in pending)))
        if new == "closed" and t["status"] != "resolved":
            raise _Rule("only a resolved ticket can be closed; %s is %s" % (a["ticket_id"], t["status"]))
        if new == "in_progress" and t["assignee"] is None:
            raise _Rule("a ticket needs an assignee before it can be in_progress")
        t["status"] = new
        return {"updated": self._full(a["ticket_id"])}

    def _t_edit_labels(self, a):
        t = self._tk(a["ticket_id"])
        add, rem = a.get("add", []), a.get("remove", [])
        if not add and not rem:
            raise _Rule("give at least one label to add or remove")
        self._labels_ok(add + rem)
        t["labels"] = sorted((set(t["labels"]) - set(rem)) | set(add))
        return {"updated": self._full(a["ticket_id"])}

    def _depends(self, start, target):
        seen, todo = set(), [start]
        while todo:
            cur = todo.pop()
            if cur == target:
                return True
            if cur in seen:
                continue
            seen.add(cur)
            todo.extend(self.state["tickets"][cur]["depends_on"])
        return False

    def _t_link_dependency(self, a):
        t = self._tk(a["ticket_id"])
        self._tk(a["depends_on_id"])
        if a["ticket_id"] == a["depends_on_id"]:
            raise _Rule("a ticket cannot depend on itself")
        if a["action"] == "remove":
            if a["depends_on_id"] not in t["depends_on"]:
                raise _Rule("%s does not depend on %s" % (a["ticket_id"], a["depends_on_id"]))
            t["depends_on"].remove(a["depends_on_id"])
        else:
            if self._depends(a["depends_on_id"], a["ticket_id"]):
                raise _Rule("circular dependency: %s already depends (directly or indirectly) on %s" % (
                    a["depends_on_id"], a["ticket_id"]))
            t["depends_on"] = sorted(set(t["depends_on"]) | set([a["depends_on_id"]]))
        return {"updated": self._full(a["ticket_id"])}

    def _t_move_to_sprint(self, a):
        t = self._tk(a["ticket_id"])
        sid = a["sprint_id"]
        if sid is not None:
            sp = self.state["sprints"].get(sid)
            if sp is None:
                raise _Rule("unknown sprint '%s'" % sid)
            if sp["state"] == "closed":
                raise _Rule("sprint %s is closed" % sid)
            used = self._used(sid, a["ticket_id"])
            if used + t["estimate"] > sp["capacity"]:
                raise _Rule("sprint %s has %d of %d points committed; a ticket of %d points does not fit" % (
                    sid, used, sp["capacity"], t["estimate"]))
        t["sprint"] = sid
        return {"updated": self._full(a["ticket_id"])}


# --------------------------------------------------------------------------
# 4. file tree
# --------------------------------------------------------------------------
_TAGS = ["archive", "confidential", "draft", "final", "review"]


def _parent(p):
    idx = p.rfind("/")
    return p[:idx] or "/"


def _base(p):
    return p[p.rfind("/") + 1:]


def _join(folder, name):
    return ("" if folder == "/" else folder) + "/" + name


def _ext(name):
    return name[name.rfind("."):].lower() if "." in name else ""


class FilesEnv(_Env):
    TOOLS = [
        _fn("list_folder", "List the subfolders and files directly inside a folder.",
            {"path": _s("Absolute folder path, e.g. /reports.")}, ["path"]),
        _fn("search_files",
            "Find files anywhere under a folder (recursive). All filters optional.",
            {"name_contains": _s("Case-insensitive text that must appear in the file name."),
             "tag": _s("Only files with this tag.", _TAGS),
             "under": _s("Folder to search in, including its subfolders. Default '/'.")}),
        _fn("get_file_info", "Size, modified date, tags and lock state of one file.",
            {"path": _s("Absolute file path.")}, ["path"]),
        _fn("create_folder", "Create a folder. Its parent folder must already exist.",
            {"path": _s("Absolute path of the new folder.")}, ["path"]),
        _fn("move", "Move a file or folder into another existing folder, optionally giving it a new name.",
            {"src": _s("Absolute path of the file or folder to move."),
             "dest_folder": _s("Absolute path of the folder to move it into."),
             "new_name": _s("Optional new name (no slashes). A file must keep its extension.")},
            ["src", "dest_folder"]),
        _fn("rename", "Rename a file or folder in place.",
            {"path": _s("Absolute path of the file or folder."),
             "new_name": _s("New name (no slashes). A file must keep its extension.")}, ["path", "new_name"]),
        _fn("copy_file", "Copy a file (with its tags; the copy is unlocked) into an existing folder.",
            {"src": _s("Absolute path of the file to copy."),
             "dest_folder": _s("Absolute path of the folder to copy into."),
             "new_name": _s("Optional name for the copy; must keep the extension.")},
            ["src", "dest_folder"]),
        _fn("set_tags", "Add and/or remove tags on a file. A file cannot be both draft and final.",
            {"path": _s("Absolute file path."),
             "add": _arr("Tags to add.", {"type": "string", "enum": _TAGS}),
             "remove": _arr("Tags to remove.", {"type": "string", "enum": _TAGS})}, ["path"]),
        _fn("set_lock", "Lock or unlock a file. Locked files cannot be moved, renamed or deleted.",
            {"path": _s("Absolute file path."),
             "locked": {"type": "boolean", "description": "true to lock, false to unlock."}}, ["path", "locked"]),
        _fn("delete", "Delete a file, or an empty folder.",
            {"path": _s("Absolute path of the file or empty folder.")}, ["path"]),
    ]

    def _p(self, path):
        if not path.startswith("/"):
            raise _Rule("paths must be absolute and start with '/': got '%s'" % path)
        if path != "/":
            path = path.rstrip("/") or "/"
        if "//" in path:
            raise _Rule("malformed path '%s'" % path)
        return path

    def _name(self, name):
        if not name or "/" in name or name in (".", ".."):
            raise _Rule("invalid name '%s' (must be non-empty, without '/')" % name)
        return name

    def _folder(self, path):
        path = self._p(path)
        if path not in self.state["folders"]:
            if path in self.state["files"]:
                raise _Rule("'%s' is a file, not a folder" % path)
            raise _Rule("folder '%s' does not exist" % path)
        return path

    def _file(self, path):
        path = self._p(path)
        if path not in self.state["files"]:
            if path in self.state["folders"]:
                raise _Rule("'%s' is a folder, not a file" % path)
            raise _Rule("file '%s' does not exist" % path)
        return path

    def _exists(self, path):
        return path in self.state["files"] or path in self.state["folders"]

    def _info(self, path):
        f = self.state["files"][path]
        return {"path": path, "size_mb": f["size_mb"], "modified": f["modified"],
                "tags": list(f["tags"]), "locked": f["locked"]}

    def _t_list_folder(self, a):
        p = self._folder(a["path"])
        subs = sorted(_base(f) for f in self.state["folders"] if f != "/" and _parent(f) == p)
        files = []
        for f in sorted(self.state["files"]):
            if _parent(f) == p:
                d = self._info(f)
                d["name"] = _base(f)
                files.append(d)
        return {"path": p, "subfolders": subs, "files": files}

    def _t_search_files(self, a):
        under = self._folder(a.get("under", "/"))
        pre = "/" if under == "/" else under + "/"
        q = a.get("name_contains", "").lower()
        out = []
        for f in sorted(self.state["files"]):
            if not f.startswith(pre):
                continue
            if q and q not in _base(f).lower():
                continue
            if "tag" in a and a["tag"] not in self.state["files"][f]["tags"]:
                continue
            out.append(self._info(f))
        return {"count": len(out), "files": out}

    def _t_get_file_info(self, a):
        return self._info(self._file(a["path"]))

    def _t_create_folder(self, a):
        p = self._p(a["path"])
        if self._exists(p):
            raise _Rule("'%s' already exists" % p)
        self._name(_base(p))
        if _parent(p) not in self.state["folders"]:
            raise _Rule("parent folder '%s' does not exist" % _parent(p))
        self.state["folders"] = sorted(self.state["folders"] + [p])
        return {"created": p}

    def _relocate(self, src, dest, new_name):
        st = self.state
        src = self._p(src)
        dest = self._folder(dest)
        name = self._name(new_name) if new_name is not None else _base(src)
        target = _join(dest, name)
        if src in st["files"]:
            if st["files"][src]["locked"]:
                raise _Rule("'%s' is locked" % src)
            if _ext(name) != _ext(_base(src)):
                raise _Rule("a file must keep its extension ('%s')" % _ext(_base(src)))
            if target == src:
                raise _Rule("'%s' is already there under that name" % src)
            if self._exists(target):
                raise _Rule("'%s' already exists" % target)
            st["files"][target] = st["files"].pop(src)
        elif src in st["folders"]:
            if src == "/":
                raise _Rule("the root folder cannot be moved or renamed")
            if dest == src or dest.startswith(src + "/"):
                raise _Rule("cannot move a folder into itself")
            if target == src:
                raise _Rule("'%s' is already there under that name" % src)
            if self._exists(target):
                raise _Rule("'%s' already exists" % target)
            inside = [f for f in st["files"] if f.startswith(src + "/")]
            locked = sorted(f for f in inside if st["files"][f]["locked"])
            if locked:
                raise _Rule("folder contains locked file(s): %s" % ", ".join(locked))
            for f in inside:
                st["files"][target + f[len(src):]] = st["files"].pop(f)
            st["folders"] = sorted(
                (target + f[len(src):]) if (f == src or f.startswith(src + "/")) else f for f in st["folders"])
        else:
            raise _Rule("'%s' does not exist" % src)
        return {"moved": src, "now_at": target}

    def _t_move(self, a):
        return self._relocate(a["src"], a["dest_folder"], a.get("new_name"))

    def _t_rename(self, a):
        p = self._p(a["path"])
        if p == "/":
            raise _Rule("the root folder cannot be moved or renamed")
        return self._relocate(p, _parent(p), a["new_name"])

    def _t_copy_file(self, a):
        st = self.state
        src = self._file(a["src"])
        dest = self._folder(a["dest_folder"])
        name = self._name(a["new_name"]) if "new_name" in a else _base(src)
        if _ext(name) != _ext(_base(src)):
            raise _Rule("the copy must keep the extension ('%s')" % _ext(_base(src)))
        target = _join(dest, name)
        if self._exists(target):
            raise _Rule("'%s' already exists" % target)
        f = copy.deepcopy(st["files"][src])
        f["locked"] = False
        f["modified"] = st["today"]
        st["files"][target] = f
        return {"created": self._info(target)}

    def _t_set_tags(self, a):
        p = self._file(a["path"])
        add, rem = a.get("add", []), a.get("remove", [])
        if not add and not rem:
            raise _Rule("give at least one tag to add or remove")
        tags = (set(self.state["files"][p]["tags"]) - set(rem)) | set(add)
        if "draft" in tags and "final" in tags:
            raise _Rule("a file cannot be tagged both draft and final; remove one of them")
        self.state["files"][p]["tags"] = sorted(tags)
        return self._info(p)

    def _t_set_lock(self, a):
        p = self._file(a["path"])
        self.state["files"][p]["locked"] = a["locked"]
        return self._info(p)

    def _t_delete(self, a):
        st = self.state
        p = self._p(a["path"])
        if p in st["files"]:
            if st["files"][p]["locked"]:
                raise _Rule("'%s' is locked" % p)
            st["trash"].append(p)
            del st["files"][p]
        elif p in st["folders"]:
            if p == "/":
                raise _Rule("the root folder cannot be deleted")
            if any(f.startswith(p + "/") for f in list(st["files"]) + st["folders"]):
                raise _Rule("folder '%s' is not empty" % p)
            st["folders"] = [f for f in st["folders"] if f != p]
        else:
            raise _Rule("'%s' does not exist" % p)
        return {"deleted": p}


# --------------------------------------------------------------------------
# 5. clinic appointments
# --------------------------------------------------------------------------
_TYPES = ["checkup", "follow_up", "vaccination", "consult"]
_FLAGS = ["deposit_required", "interpreter", "no_show_warning", "vip"]


class ClinicEnv(_Env):
    TOOLS = [
        _fn("get_clinic_info",
            "Today's date and weekday, opening hours, the fixed duration of each appointment type, and the "
            "clinicians with the weekdays they work and the appointment types they offer."),
        _fn("find_patients",
            "Look up patients by (part of) their name. An empty query lists all patients. Returns id, name, "
            "date of birth, phone and flags.",
            {"query": _s("Case-insensitive part of a name, or empty for everyone.")}, ["query"]),
        _fn("list_appointments",
            "List appointments. Give at least one filter; filters are combined with AND.",
            {"date": _s("Only this date, YYYY-MM-DD."), "clinician_id": _s("Only this clinician."),
             "patient_id": _s("Only this patient."),
             "status": _s("Only this status.", ["booked", "cancelled", "completed", "no_show"])}),
        _fn("book_appointment",
            "Book an appointment. Duration follows from the type. Fails if the clinician does not work that day, "
            "does not offer the type, or if clinician or patient has an overlapping booked appointment.",
            {"patient_id": _s("Patient id."), "clinician_id": _s("Clinician id."),
             "date": _s("Date, YYYY-MM-DD."), "time": _s("Start time HH:MM (15-minute steps)."),
             "type": _s("Appointment type.", _TYPES)},
            ["patient_id", "clinician_id", "date", "time", "type"]),
        _fn("reschedule_appointment",
            "Move a booked appointment to another date, time and/or clinician. Same rules as booking.",
            {"appointment_id": _s("Appointment id, e.g. A501."),
             "new": {"type": "object", "description": "What changes; omit fields that stay the same.",
                     "properties": {"date": _s("New date, YYYY-MM-DD."), "time": _s("New start time, HH:MM."),
                                    "clinician_id": _s("New clinician id.")},
                     "additionalProperties": False}},
            ["appointment_id", "new"]),
        _fn("cancel_appointment", "Cancel a booked appointment.",
            {"appointment_id": _s("Appointment id."),
             "reason": _s("Reason code.", ["patient_request", "clinician_unavailable", "duplicate", "other"])},
            ["appointment_id", "reason"]),
        _fn("set_appointment_status",
            "Record the outcome of a booked appointment dated today or earlier.",
            {"appointment_id": _s("Appointment id."), "status": _s("Outcome.", ["completed", "no_show"])},
            ["appointment_id", "status"]),
        _fn("update_patient", "Change a patient's phone number and/or flags.",
            {"patient_id": _s("Patient id."),
             "fields": {"type": "object", "description": "What to change.",
                        "properties": {"phone": _s("New phone number."),
                                       "add_flags": _arr("Flags to add.", {"type": "string", "enum": _FLAGS}),
                                       "remove_flags": _arr("Flags to remove.", {"type": "string", "enum": _FLAGS})},
                        "additionalProperties": False}},
            ["patient_id", "fields"]),
        _fn("list_waitlist", "The waitlist in order (first entry is first in line), optionally for one clinician.",
            {"clinician_id": _s("Only entries waiting for this clinician.")}),
        _fn("manage_waitlist", "Add a patient to the end of a clinician's waitlist, or remove their entry.",
            {"action": _s("add or remove.", ["add", "remove"]), "patient_id": _s("Patient id."),
             "clinician_id": _s("Clinician id."), "type": _s("Appointment type waited for.", _TYPES)},
            ["action", "patient_id", "clinician_id", "type"]),
    ]

    def _appt(self, aid):
        ap = self.state["appointments"].get(aid)
        if ap is None:
            raise _Rule("unknown appointment '%s'" % aid)
        return ap

    def _patient(self, pid):
        if pid not in self.state["patients"]:
            raise _Rule("unknown patient '%s'" % pid)
        return self.state["patients"][pid]

    def _clin(self, cid):
        if cid not in self.state["clinicians"]:
            raise _Rule("unknown clinician '%s'" % cid)
        return self.state["clinicians"][cid]

    def _view(self, aid):
        ap = self.state["appointments"][aid]
        s = _ptime(ap["time"])
        return {"appointment_id": aid, "patient_id": ap["patient"],
                "patient_name": self.state["patients"][ap["patient"]]["name"],
                "clinician_id": ap["clinician"], "date": ap["date"], "time": ap["time"],
                "end_time": _hm(s + self.state["durations"][ap["type"]]), "type": ap["type"],
                "status": ap["status"], "cancel_reason": ap["cancel_reason"]}

    def _slot_ok(self, ap, aid):
        st = self.state
        self._patient(ap["patient"])
        cl = self._clin(ap["clinician"])
        d = _pdate(ap["date"])
        if ap["date"] < st["today"]:
            raise _Rule("%s is in the past (today is %s)" % (ap["date"], st["today"]))
        if _DAYS[d.weekday()] not in cl["works"]:
            raise _Rule("%s (%s) does not work on %s (%s); works: %s" % (
                ap["clinician"], cl["name"], ap["date"], _DAYNAMES[d.weekday()], ", ".join(cl["works"])))
        if ap["type"] not in cl["services"]:
            raise _Rule("%s (%s) does not offer %s appointments" % (ap["clinician"], cl["name"], ap["type"]))
        s = _ptime(ap["time"])
        e = s + st["durations"][ap["type"]]
        if s % 15:
            raise _Rule("appointments start on 15-minute steps")
        if s < _ptime(st["hours"]["open"]) or e > _ptime(st["hours"]["close"]):
            raise _Rule("appointment must be within opening hours %s-%s" % (st["hours"]["open"], st["hours"]["close"]))
        for oid in sorted(st["appointments"]):
            o = st["appointments"][oid]
            if oid == aid or o["status"] != "booked" or o["date"] != ap["date"]:
                continue
            os_ = _ptime(o["time"])
            oe = os_ + st["durations"][o["type"]]
            if not (s < oe and os_ < e):
                continue
            if o["clinician"] == ap["clinician"]:
                raise _Rule("%s is busy then: %s (%s-%s)" % (ap["clinician"], oid, o["time"], _hm(oe)))
            if o["patient"] == ap["patient"]:
                raise _Rule("patient %s has an overlapping appointment: %s with %s (%s-%s)" % (
                    ap["patient"], oid, o["clinician"], o["time"], _hm(oe)))

    def _t_get_clinic_info(self, a):
        st = self.state
        d = _pdate(st["today"])
        return {"today": st["today"], "weekday": _DAYNAMES[d.weekday()], "opening_hours": dict(st["hours"]),
                "duration_minutes": dict(st["durations"]),
                "clinicians": [{"clinician_id": k, "name": v["name"], "works": list(v["works"]),
                                "services": list(v["services"])} for k, v in sorted(st["clinicians"].items())]}

    def _t_find_patients(self, a):
        q = a["query"].strip().lower()
        return {"patients": [{"patient_id": k, "name": v["name"], "date_of_birth": v["dob"], "phone": v["phone"],
                              "flags": list(v["flags"])}
                             for k, v in sorted(self.state["patients"].items()) if q in v["name"].lower()]}

    def _t_list_appointments(self, a):
        if not a:
            raise _Rule("give at least one filter (date, clinician_id, patient_id or status)")
        if "date" in a:
            _pdate(a["date"])
        if "clinician_id" in a:
            self._clin(a["clinician_id"])
        if "patient_id" in a:
            self._patient(a["patient_id"])
        ids = []
        for k, v in self.state["appointments"].items():
            if "date" in a and v["date"] != a["date"]:
                continue
            if "clinician_id" in a and v["clinician"] != a["clinician_id"]:
                continue
            if "patient_id" in a and v["patient"] != a["patient_id"]:
                continue
            if "status" in a and v["status"] != a["status"]:
                continue
            ids.append(k)
        ids.sort(key=lambda k: (self.state["appointments"][k]["date"], self.state["appointments"][k]["time"], k))
        return {"count": len(ids), "appointments": [self._view(k) for k in ids]}

    def _t_book_appointment(self, a):
        st = self.state
        ap = {"patient": a["patient_id"], "clinician": a["clinician_id"], "date": a["date"], "time": a["time"],
              "type": a["type"], "status": "booked", "cancel_reason": None}
        self._slot_ok(ap, None)
        aid = "A%d" % st["next_appt"]
        st["next_appt"] += 1
        st["appointments"][aid] = ap
        return {"booked": self._view(aid)}

    def _t_reschedule_appointment(self, a):
        ap = self._appt(a["appointment_id"])
        if ap["status"] != "booked":
            raise _Rule("%s is %s; only booked appointments can be rescheduled" % (a["appointment_id"], ap["status"]))
        new = a["new"]
        if not new:
            raise _Rule("'new' is empty; give date, time and/or clinician_id")
        if "date" in new:
            ap["date"] = new["date"]
        if "time" in new:
            ap["time"] = new["time"]
        if "clinician_id" in new:
            ap["clinician"] = new["clinician_id"]
        self._slot_ok(ap, a["appointment_id"])
        return {"rescheduled": self._view(a["appointment_id"])}

    def _t_cancel_appointment(self, a):
        ap = self._appt(a["appointment_id"])
        if ap["status"] != "booked":
            raise _Rule("%s is %s; only booked appointments can be cancelled" % (a["appointment_id"], ap["status"]))
        ap["status"] = "cancelled"
        ap["cancel_reason"] = a["reason"]
        return {"cancelled": self._view(a["appointment_id"])}

    def _t_set_appointment_status(self, a):
        ap = self._appt(a["appointment_id"])
        if ap["status"] != "booked":
            raise _Rule("%s is already %s" % (a["appointment_id"], ap["status"]))
        if ap["date"] > self.state["today"]:
            raise _Rule("%s is in the future (%s); no outcome can be recorded yet" % (a["appointment_id"], ap["date"]))
        ap["status"] = a["status"]
        return {"updated": self._view(a["appointment_id"])}

    def _t_update_patient(self, a):
        p = self._patient(a["patient_id"])
        f = a["fields"]
        if not f:
            raise _Rule("fields is empty; give phone, add_flags and/or remove_flags")
        if "phone" in f:
            if not f["phone"].strip():
                raise _Rule("phone must not be empty")
            p["phone"] = f["phone"].strip()
        p["flags"] = sorted((set(p["flags"]) - set(f.get("remove_flags", []))) | set(f.get("add_flags", [])))
        return {"patient_id": a["patient_id"], "name": p["name"], "phone": p["phone"], "flags": list(p["flags"])}

    def _t_list_waitlist(self, a):
        if "clinician_id" in a:
            self._clin(a["clinician_id"])
        out = []
        for n, w in enumerate(self.state["waitlist"]):
            if "clinician_id" in a and w["clinician"] != a["clinician_id"]:
                continue
            out.append({"position": n + 1, "patient_id": w["patient"],
                        "patient_name": self.state["patients"][w["patient"]]["name"],
                        "clinician_id": w["clinician"], "type": w["type"]})
        return {"waitlist": out}

    def _t_manage_waitlist(self, a):
        self._patient(a["patient_id"])
        self._clin(a["clinician_id"])
        entry = {"patient": a["patient_id"], "clinician": a["clinician_id"], "type": a["type"]}
        wl = self.state["waitlist"]
        if a["action"] == "add":
            if entry in wl:
                raise _Rule("that patient is already on this waitlist for that type")
            wl.append(entry)
        else:
            if entry not in wl:
                raise _Rule("no such waitlist entry")
            wl.remove(entry)
        return {"waitlist_length": len(wl)}


ENVS = {"inventory": InventoryEnv, "calendar": CalendarEnv, "tickets": TicketEnv,
        "files": FilesEnv, "clinic": ClinicEnv}


# --------------------------------------------------------------------------
# check helpers
# --------------------------------------------------------------------------
def _n(text):
    return " ".join(text.strip().lower().split()) if isinstance(text, str) else None


def _ti(title):
    return lambda v: _n(v) == _n(title)


def _fits(rec, want):
    for k, v in want.items():
        if callable(v):
            if not v(rec.get(k)):
                return False
        elif rec.get(k) != v:
            return False
    return True


def _match(fresh, wants):
    if len(fresh) != len(wants):
        return False
    for perm in itertools.permutations(range(len(fresh))):
        if all(_fits(fresh[perm[n]], wants[n]) for n in range(len(wants))):
            return True
    return False


def _final(s, i, changes=None, new=None):
    """True iff state s equals init i except for exactly the described differences.

    changes: {top_key: {record_id: {field: value} | None(deleted)}} for dict collections,
             {top_key: expected_value | predicate} for anything else.
    new:     {top_key: [ {field: value | predicate}, ... ]} records that must have been created
             (matched by content, ids ignored). Collections not listed must have no new records.
    Counters (next_*) are ignored.
    """
    changes = changes or {}
    new = new or {}
    if set(s.keys()) != set(i.keys()):
        return False
    for key in i:
        if key.startswith("next_"):
            continue
        if isinstance(i[key], dict):
            if not isinstance(s[key], dict):
                return False
            exp = copy.deepcopy(i[key])
            for rid, ch in changes.get(key, {}).items():
                if ch is None:
                    del exp[rid]
                else:
                    exp[rid].update(ch)
            got = dict((k, v) for k, v in s[key].items() if k in i[key])
            if got != exp:
                return False
            fresh = [s[key][k] for k in sorted(s[key]) if k not in i[key]]
            if not _match(fresh, new.get(key, [])):
                return False
        elif key in changes:
            want = changes[key]
            if callable(want):
                if not want(s[key]):
                    return False
            elif s[key] != want:
                return False
        elif s[key] != i[key]:
            return False
    return True


def _adj_net(want):
    """Predicate over the adjustments log: net delta per (sku, location, reason) equals want."""
    def pred(log):
        net = {}
        for a in log:
            k = (a["sku"], a["location"], a["reason"])
            net[k] = net.get(k, 0) + a["delta"]
        return dict((k, v) for k, v in net.items() if v != 0) == want
    return pred


def _fs_check(s, i, mut, loose=()):
    """Files env: expected = init files/folders after mut(files, folders); trash is ignored."""
    files = copy.deepcopy(i["files"])
    folders = set(i["folders"])
    mut(files, folders)
    if s.get("today") != i["today"] or set(s["folders"]) != folders or set(s["files"]) != set(files):
        return False
    for p in files:
        a, b = dict(s["files"][p]), dict(files[p])
        if p in loose:
            a.pop("modified", None)
            b.pop("modified", None)
        if a != b:
            return False
    return True


TASKS = []


def _add(tid, env, difficulty, init, prompt, reference, trap, check, ref_errors=()):
    frozen = copy.deepcopy(init)
    TASKS.append({
        "id": tid, "env": env, "difficulty": difficulty, "init": init, "prompt": prompt,
        "reference": reference, "ref_errors": list(ref_errors), "trap": trap,
        "check": (lambda state, _c=check, _i=frozen: bool(_c(state, _i))),
    })


# --------------------------------------------------------------------------
# inventory fixtures + tasks T01-T08
# --------------------------------------------------------------------------
def _inv():
    def item(name, sup, pack, rp, main, annex, quar=0):
        return {"name": name, "supplier": sup, "pack_size": pack, "reorder_point": rp,
                "stock": {"MAIN": main, "ANNEX": annex, "QUAR": quar},
                "flags": {"reviewed": False, "hold": False, "discontinued": False}}

    def po(sup, created, expected, lines, status="open", reason=None):
        return {"supplier": sup, "created": created, "expected": expected, "status": status,
                "cancel_reason": reason, "lines": lines}

    return {
        "today": "2026-03-09",
        "locations": ["MAIN", "ANNEX", "QUAR"],
        "suppliers": {
            "SUP-01": {"name": "Brightline Fasteners", "min_line_qty": 50, "active": True},
            "SUP-02": {"name": "Kestrel Packaging", "min_line_qty": 12, "active": True},
            "SUP-03": {"name": "Kestrel Paper Co", "min_line_qty": 10, "active": True},
            "SUP-04": {"name": "Orrin Seals", "min_line_qty": 50, "active": True},
            "SUP-05": {"name": "Halvorsen Tools", "min_line_qty": 5, "active": False},
        },
        "items": {
            "HB-0840": item("Hex bolt M8x40 zinc", "SUP-01", 25, 60, 140, 35),
            "HB-0845": item("Hex bolt M8x45 zinc", "SUP-01", 25, 60, 20, 10),
            "HB-0840S": item("Hex bolt M8x40 stainless", "SUP-01", 25, 60, 30, 12),
            "WN-08": item("Wing nut M8", "SUP-01", 10, 40, 80, 0),
            "OR-20N": item("O-ring 20mm nitrile", "SUP-04", 50, 150, 90, 0),
            "OR-20V": item("O-ring 20mm viton", "SUP-04", 50, 50, 60, 20),
            "SW-400C": item("Shrink wrap 400mm clear", "SUP-02", 6, 12, 4, 0),
            "SW-400B": item("Shrink wrap 400mm black", "SUP-02", 6, 12, 18, 6),
            "CT-48": item("Carton tape 48mm", "SUP-02", 12, 48, 70, 20, 5),
            "CT-72": item("Carton tape 72mm", "SUP-02", 12, 24, 36, 0),
            "LB-A6": item("Label roll A6", "SUP-03", 10, 30, 60, 14),
            "LB-A5": item("Label roll A5", "SUP-03", 10, 30, 57, 18),
            "KP-30": item("Kraft paper roll 30gsm", "SUP-03", 5, 10, 9, 0),
        },
        "purchase_orders": {
            "PO-1000": po("SUP-01", "2026-02-01", "2026-02-15", {"HB-0845": 50}, "cancelled", "other"),
            "PO-1001": po("SUP-04", "2026-02-20", "2026-03-16", {"OR-20N": 100, "OR-20V": 50}),
            "PO-1002": po("SUP-02", "2026-02-24", "2026-03-05", {"SW-400C": 12, "CT-48": 24}),
            "PO-1003": po("SUP-03", "2026-02-25", "2026-03-09", {"LB-A6": 20}),
            "PO-1004": po("SUP-01", "2026-02-27", "2026-03-02", {"WN-08": 50}),
        },
        "adjustments": [],
        "next_po": 1005,
    }


_add("T01", "inventory", "medium", _inv(),
     "We might be running low on the stainless M8x40 hex bolts. Add up what we hold across all locations. "
     "If that total is below the item's reorder point, raise a new purchase order with its supplier for just "
     "that item: enough whole packs to bring the total on hand up to at least twice the reorder point, and not "
     "a pack more. If the total is at or above the reorder point, don't order anything and flag the item as "
     "reviewed instead. Don't flag it if you order.",
     [["list_items", {"query": "hex bolt"}], ["get_item", {"sku": "HB-0840S"}],
      ["create_purchase_order", {"supplier_id": "SUP-01", "lines": [{"sku": "HB-0840S", "qty": 100}]}]],
     [["get_item", {"sku": "HB-0840"}], ["set_item_flag", {"sku": "HB-0840S", "flag": "reviewed", "value": True}]],
     lambda s, i: _final(s, i, new={"purchase_orders": [
         {"supplier": "SUP-01", "status": "open", "lines": {"HB-0840S": 100}}]}))

_add("T02", "inventory", "hard", _inv(),
     "Across our open purchase orders we should have exactly 300 of the nitrile 20mm O-rings on order in total; "
     "right now it's fewer. Please fix that. Don't cancel any purchase order, don't end up with the item on more "
     "than one order, and leave every other line and every other order exactly as it is.",
     [["list_items", {"query": "o-ring"}], ["list_purchase_orders", {"status": "open"}],
      ["create_purchase_order", {"supplier_id": "SUP-04", "lines": [{"sku": "OR-20N", "qty": 200}]}],
      ["set_po_line", {"po_id": "PO-1001", "sku": "OR-20N", "qty": 300}]],
     [["set_po_line", {"po_id": "PO-1001", "sku": "OR-20V", "qty": 300}]],
     lambda s, i: _final(s, i, changes={"purchase_orders": {
         "PO-1001": {"lines": {"OR-20N": 300, "OR-20V": 50}}}}),
     ref_errors=[2])

_add("T03", "inventory", "hard", _inv(),
     "Six rolls of the 48mm carton tape in MAIN got crushed by a forklift. Write those six off as damaged. Once "
     "that's done, even the tape out between MAIN and ANNEX so that the two locations hold exactly the same "
     "quantity of it. Whatever is sitting in QUAR must stay there, and the 72mm tape is not affected.",
     [["list_items", {"query": "carton tape"}], ["get_item", {"sku": "CT-48"}],
      ["adjust_stock", {"sku": "CT-48", "location": "MAIN", "delta": -6, "reason": "damaged"}],
      ["transfer_stock", {"sku": "CT-48", "from_location": "MAIN", "to_location": "ANNEX", "qty": 22}]],
     [["adjust_stock", {"sku": "CT-48", "location": "MAIN", "delta": -6, "reason": "damaged"}],
      ["transfer_stock", {"sku": "CT-48", "from_location": "MAIN", "to_location": "ANNEX", "qty": 25}]],
     lambda s, i: _final(s, i, changes={
         "items": {"CT-48": {"stock": {"MAIN": 42, "ANNEX": 42, "QUAR": 5}}},
         "adjustments": _adj_net({("CT-48", "MAIN", "damaged"): -6})}))

_add("T04", "inventory", "hard", _inv(),
     "We're dropping the clear 400mm shrink wrap from the range. Mark it discontinued. The system won't let you "
     "while we still hold any or have it on order, so: write off whatever stock is left as expired, and if it "
     "sits on an open purchase order, remove just that line and keep the rest of that order open as it is. The "
     "black 400mm shrink wrap stays active and untouched.",
     [["list_items", {"query": "shrink wrap"}], ["get_item", {"sku": "SW-400C"}],
      ["set_item_flag", {"sku": "SW-400C", "flag": "discontinued", "value": True}],
      ["adjust_stock", {"sku": "SW-400C", "location": "MAIN", "delta": -4, "reason": "expired"}],
      ["list_purchase_orders", {"status": "open"}],
      ["set_po_line", {"po_id": "PO-1002", "sku": "SW-400C", "qty": 0}],
      ["set_item_flag", {"sku": "SW-400C", "flag": "discontinued", "value": True}]],
     [["adjust_stock", {"sku": "SW-400C", "location": "MAIN", "delta": -4, "reason": "expired"}],
      ["cancel_purchase_order", {"po_id": "PO-1002", "reason": "no_longer_needed"}],
      ["set_item_flag", {"sku": "SW-400C", "flag": "discontinued", "value": True}]],
     lambda s, i: _final(s, i, changes={
         "items": {"SW-400C": {"stock": {"MAIN": 0, "ANNEX": 0, "QUAR": 0},
                               "flags": {"reviewed": False, "hold": False, "discontinued": True}}},
         "purchase_orders": {"PO-1002": {"lines": {"CT-48": 24}}},
         "adjustments": _adj_net({("SW-400C", "MAIN", "expired"): -4})}),
     ref_errors=[2])


def _inv05():
    st = _inv()
    del st["purchase_orders"]["PO-1001"]
    it = st["items"]
    it["OR-20N"].update({"pack_size": 10, "reorder_point": 40, "stock": {"MAIN": 9, "ANNEX": 4, "QUAR": 0}})
    it["OR-20V"].update({"pack_size": 10, "reorder_point": 30, "stock": {"MAIN": 44, "ANNEX": 20, "QUAR": 0}})
    it["OR-35N"] = {"name": "O-ring 35mm nitrile", "supplier": "SUP-04", "pack_size": 5, "reorder_point": 15,
                    "stock": {"MAIN": 11, "ANNEX": 0, "QUAR": 0},
                    "flags": {"reviewed": False, "hold": False, "discontinued": False}}
    return st


_add("T05", "inventory", "very hard", _inv05(),
     "Go through every item we buy from Orrin Seals. Where the total on hand (all locations together) is below "
     "the item's reorder point, it needs reordering: the quantity is twice the reorder point minus the total on "
     "hand, rounded up to whole packs, and if that is still under the supplier's minimum line quantity, order "
     "the minimum instead. Put all the reorders on one single new purchase order. Items that are at or above "
     "their reorder point just get flagged as reviewed. Don't flag the ones you reorder.",
     [["get_warehouse_info", {}], ["list_items", {"supplier_id": "SUP-04"}],
      ["get_item", {"sku": "OR-20N"}], ["get_item", {"sku": "OR-20V"}], ["get_item", {"sku": "OR-35N"}],
      ["create_purchase_order", {"supplier_id": "SUP-04", "lines": [{"sku": "OR-20N", "qty": 70},
                                                                    {"sku": "OR-35N", "qty": 20}]}],
      ["create_purchase_order", {"supplier_id": "SUP-04", "lines": [{"sku": "OR-20N", "qty": 70},
                                                                    {"sku": "OR-35N", "qty": 50}]}],
      ["set_item_flag", {"sku": "OR-20V", "flag": "reviewed", "value": True}]],
     [["create_purchase_order", {"supplier_id": "SUP-04", "lines": [{"sku": "OR-20N", "qty": 70},
                                                                    {"sku": "OR-35N", "qty": 50}]}],
      ["set_item_flag", {"sku": "OR-20V", "flag": "reviewed", "value": True}],
      ["set_item_flag", {"sku": "OR-20N", "flag": "reviewed", "value": True}],
      ["set_item_flag", {"sku": "OR-35N", "flag": "reviewed", "value": True}]],
     lambda s, i: _final(s, i, changes={
         "items": {"OR-20V": {"flags": {"reviewed": True, "hold": False, "discontinued": False}}}},
         new={"purchase_orders": [{"supplier": "SUP-04", "status": "open",
                                   "lines": {"OR-20N": 70, "OR-35N": 50}}]}),
     ref_errors=[5])

_add("T06", "inventory", "medium", _inv(),
     "Chase-up day. Find out today's date from the system, then cancel every open purchase order whose expected "
     "date is strictly before today, giving the reason supplier_delay. Orders expected today or later stay open, "
     "and orders that are already cancelled should be left exactly as they are, whatever their dates.",
     [["get_warehouse_info", {}], ["list_purchase_orders", {"status": "open"}],
      ["cancel_purchase_order", {"po_id": "PO-1002", "reason": "supplier_delay"}],
      ["cancel_purchase_order", {"po_id": "PO-1004", "reason": "supplier_delay"}]],
     [["cancel_purchase_order", {"po_id": "PO-1002", "reason": "supplier_delay"}],
      ["cancel_purchase_order", {"po_id": "PO-1004", "reason": "supplier_delay"}],
      ["cancel_purchase_order", {"po_id": "PO-1003", "reason": "supplier_delay"}]],
     lambda s, i: _final(s, i, changes={"purchase_orders": {
         "PO-1002": {"status": "cancelled", "cancel_reason": "supplier_delay"},
         "PO-1004": {"status": "cancelled", "cancel_reason": "supplier_delay"}}}))

_add("T07", "inventory", "hard", _inv(),
     "Cycle count results for the A6 label rolls: 57 in MAIN and 18 in ANNEX. Bring the system quantities in "
     "line with the count using count corrections. Then compare the counted total for those two locations with "
     "what the system showed for them before your corrections: if the counted total is lower, put the item on "
     "hold; if it is the same or higher, flag it reviewed instead. Only one of the two flags should end up set.",
     [["list_items", {"query": "label roll"}], ["get_item", {"sku": "LB-A6"}],
      ["adjust_stock", {"sku": "LB-A6", "location": "MAIN", "delta": -3, "reason": "count_correction"}],
      ["adjust_stock", {"sku": "LB-A6", "location": "ANNEX", "delta": 4, "reason": "count_correction"}],
      ["set_item_flag", {"sku": "LB-A6", "flag": "reviewed", "value": True}]],
     [["adjust_stock", {"sku": "LB-A6", "location": "MAIN", "delta": -3, "reason": "count_correction"}],
      ["adjust_stock", {"sku": "LB-A6", "location": "ANNEX", "delta": 4, "reason": "count_correction"}],
      ["set_item_flag", {"sku": "LB-A6", "flag": "hold", "value": True}]],
     lambda s, i: _final(s, i, changes={
         "items": {"LB-A6": {"stock": {"MAIN": 57, "ANNEX": 18, "QUAR": 0},
                             "flags": {"reviewed": True, "hold": False, "discontinued": False}}},
         "adjustments": _adj_net({("LB-A6", "MAIN", "count_correction"): -3,
                                  ("LB-A6", "ANNEX", "count_correction"): 4})}))


def _inv08():
    st = _inv()
    st["purchase_orders"]["PO-1005"] = {"supplier": "SUP-02", "created": "2026-03-06", "expected": "2026-03-20",
                                        "status": "open", "cancel_reason": None,
                                        "lines": {"CT-48": 12, "SW-400B": 18, "CT-72": 24}}
    st["next_po"] = 1006
    return st


def _c08(s, i):
    po = s["purchase_orders"].get("PO-1005", {})
    if po.get("status") != "cancelled" or po.get("cancel_reason") != "duplicate":
        return False
    return _final(s, i, changes={"purchase_orders": {
        "PO-1002": {"lines": {"SW-400C": 12, "CT-48": 36, "SW-400B": 18, "CT-72": 24}},
        "PO-1005": copy.deepcopy(po)}})   # lines left on the cancelled order do not matter


_add("T08", "inventory", "very hard", _inv08(),
     "The night shift raised a second purchase order to Kestrel Packaging by mistake, so there are now two open "
     "ones for that supplier. Merge them into the one that was created first: every line of the newer order "
     "must end up on the older one, and where the same SKU is on both, the older order's line should carry the "
     "two quantities added together. The newer order must end up cancelled with reason duplicate. Orders to "
     "other suppliers, including Kestrel Paper Co, are not part of this.",
     [["get_warehouse_info", {}], ["list_purchase_orders", {"status": "open"}],
      ["set_po_line", {"po_id": "PO-1002", "sku": "CT-48", "qty": 36}],
      ["set_po_line", {"po_id": "PO-1002", "sku": "SW-400B", "qty": 18}],
      ["cancel_purchase_order", {"po_id": "PO-1005", "reason": "duplicate"}],
      ["set_po_line", {"po_id": "PO-1002", "sku": "SW-400B", "qty": 18}],
      ["set_po_line", {"po_id": "PO-1002", "sku": "CT-72", "qty": 24}]],
     [["cancel_purchase_order", {"po_id": "PO-1002", "reason": "duplicate"}],
      ["set_po_line", {"po_id": "PO-1005", "sku": "CT-48", "qty": 36}],
      ["set_po_line", {"po_id": "PO-1005", "sku": "SW-400C", "qty": 12}]],
     _c08, ref_errors=[3])


# --------------------------------------------------------------------------
# calendar fixtures + tasks T09-T16
# --------------------------------------------------------------------------
_MON, _TUE, _WED, _THU, _FRI = "2026-04-13", "2026-04-14", "2026-04-15", "2026-04-16", "2026-04-17"


def _cal(events):
    people = [("U01", "Priya Nair", "Finance"), ("U02", "Marek Dvorak", "Infrastructure"),
              ("U03", "Lena Kowalczyk", "Operations"), ("U04", "Lena Okonkwo", "Design"),
              ("U05", "Dana Whitlock", "Sales"), ("U06", "Dana Whitfield", "Legal"),
              ("U07", "Tomas Aguilar", "Operations"), ("U08", "Sofia Brandt", "Sales"),
              ("U09", "Hiro Tanabe", "Infrastructure"), ("U10", "Elise Fontaine", "Finance"),
              ("U11", "Jonas Weber", "Procurement"), ("U12", "Amara Diallo", "People")]
    rooms = [("R-ALDER", "Alder", 4, ["video"]), ("R-BIRCH", "Birch", 2, ["video"]),
             ("R-CEDAR", "Cedar", 8, ["video", "whiteboard"]), ("R-JUNIPER", "Juniper", 6, ["video"]),
             ("R-MAPLE", "Maple", 4, ["whiteboard"]), ("R-OAK", "Oak", 12, ["projector", "video"])]
    st = {"today": _MON, "hours": {"open": "09:00", "close": "18:00"},
          "people": dict((p[0], {"name": p[1], "team": p[2]}) for p in people),
          "rooms": dict((r[0], {"name": r[1], "capacity": r[2], "features": r[3]}) for r in rooms),
          "events": {}, "next_event": 101 + len(events)}
    for n, e in enumerate(events):
        st["events"]["E%d" % (101 + n)] = {"title": e[0], "date": e[1], "start": e[2], "end": e[3],
                                           "room": e[4], "organizer": e[5],
                                           "attendees": sorted(set(e[6]) | set([e[5]]))}
    return st


_add("T09", "calendar", "medium", _cal([
    ("Forecast check", _WED, "13:30", "14:30", "R-ALDER", "U01", ["U02"]),
    ("Whitfield 1:1", _WED, "11:00", "12:00", "R-BIRCH", "U06", ["U10"]),
    ("Legal intake", _WED, "14:00", "15:00", "R-CEDAR", "U11", ["U12"]),
    ("Pricing prep", _TUE, "14:00", "15:00", "R-JUNIPER", "U08", ["U05"])]),
     "Please set up a one-hour meeting called 'Pricing review' this Wednesday from 14:00 for Dana Whitlock, "
     "Hiro Tanabe and Sofia Brandt, with Sofia as the organiser. Put it in the smallest room that has video, is "
     "big enough for the three of them and is actually free for that hour. Today's date is in the calendar "
     "system. Don't change any existing meetings.",
     [["get_calendar_info", {}], ["find_people", {"query": "Dana"}], ["find_people", {"query": "Hiro"}],
      ["find_people", {"query": "Sofia"}], ["list_rooms", {"min_capacity": 3, "feature": "video"}],
      ["list_events", {"date": _WED}],
      ["create_event", {"title": "Pricing review", "date": _WED, "start": "14:00", "end": "15:00",
                        "organizer_id": "U08", "attendee_ids": ["U05", "U09"], "room_id": "R-JUNIPER"}]],
     [["create_event", {"title": "Pricing review", "date": _WED, "start": "14:00", "end": "15:00",
                        "organizer_id": "U08", "attendee_ids": ["U06", "U09"], "room_id": "R-JUNIPER"}]],
     lambda s, i: _final(s, i, new={"events": [{
         "title": _ti("Pricing review"), "date": _WED, "start": "14:00", "end": "15:00", "room": "R-JUNIPER",
         "organizer": "U08", "attendees": ["U05", "U08", "U09"]}]}))

_add("T10", "calendar", "hard", _cal([
    ("Budget sync", _TUE, "11:00", "12:00", "R-MAPLE", "U01", ["U02", "U10", "U11"]),
    ("Budget sync (EMEA)", _TUE, "15:00", "16:00", "R-ALDER", "U12", ["U09"]),
    ("Supplier call", _THU, "11:30", "12:00", None, "U11", ["U12"]),
    ("Desk move briefing", _THU, "09:00", "09:30", "R-MAPLE", "U08", ["U07"])]),
     "Tuesday's 'Budget sync' (the main one, not the EMEA one) needs to move to Thursday this week, same start "
     "and end time, same room. If one of its attendees already has another meeting overlapping that time on "
     "Thursday, take that person off the Budget sync rather than changing their other meeting in any way. "
     "Everyone else stays on it.",
     [["get_calendar_info", {}], ["list_events", {"date": _TUE}],
      ["update_event", {"event_id": "E101", "changes": {"date": _THU}}],
      ["set_attendees", {"event_id": "E101", "remove": ["U11"]}],
      ["update_event", {"event_id": "E101", "changes": {"date": _THU}}]],
     [["update_event", {"event_id": "E103", "changes": {"start": "12:00", "end": "12:30"}}],
      ["update_event", {"event_id": "E101", "changes": {"date": _THU}}]],
     lambda s, i: _final(s, i, changes={"events": {
         "E101": {"date": _THU, "attendees": ["U01", "U02", "U10"]}}}),
     ref_errors=[2])

_add("T11", "calendar", "hard", _cal([
    ("Close prep", _FRI, "10:00", "10:45", "R-ALDER", "U01", ["U10"]),
    ("Infra standup", _FRI, "10:30", "11:30", "R-MAPLE", "U02", ["U09"]),
    ("Interview panel", _FRI, "11:30", "12:00", "R-JUNIPER", "U08", ["U12"]),
    ("Lunch and learn", _FRI, "12:30", "13:30", "R-OAK", "U10", ["U01", "U02"]),
    ("Contract review", _FRI, "09:00", "10:00", "R-JUNIPER", "U06", ["U11"])]),
     "Book 'Vendor debrief' for Priya Nair and Marek Dvorak, with Priya as organiser, in the Juniper room on "
     "Friday this week. It should last 30 minutes and start at the earliest time at or after 10:00 at which "
     "both of them and the room are free for the whole half hour. Don't move or change any other meeting to "
     "make space.",
     [["get_calendar_info", {}], ["find_people", {"query": "Priya"}], ["find_people", {"query": "Marek"}],
      ["list_events", {"date": _FRI}],
      ["create_event", {"title": "Vendor debrief", "date": _FRI, "start": "12:00", "end": "12:30",
                        "organizer_id": "U01", "attendee_ids": ["U02"], "room_id": "R-JUNIPER"}]],
     [["create_event", {"title": "Vendor debrief", "date": _FRI, "start": "13:30", "end": "14:00",
                        "organizer_id": "U01", "attendee_ids": ["U02"], "room_id": "R-JUNIPER"}]],
     lambda s, i: _final(s, i, new={"events": [{
         "title": _ti("Vendor debrief"), "date": _FRI, "start": "12:00", "end": "12:30", "room": "R-JUNIPER",
         "organizer": "U01", "attendees": ["U01", "U02"]}]}))

_add("T12", "calendar", "very hard", _cal([
    ("Roadmap review", _WED, "09:30", "10:30", "R-CEDAR", "U10", ["U01", "U09"]),
    ("Team retro", _WED, "11:00", "12:00", "R-CEDAR", "U08", ["U03", "U04", "U05", "U06", "U07"]),
    ("Hiring sync", _WED, "14:00", "14:30", "R-CEDAR", "U12", ["U11"]),
    ("Client call", _WED, "14:00", "15:00", "R-ALDER", "U02", ["U01"]),
    ("Roadmap follow-up", _THU, "10:00", "11:00", "R-CEDAR", "U10", ["U09"])]),
     "Cedar is closed for maintenance this Wednesday. Move every meeting booked in Cedar that day into Alder, "
     "keeping its time. Any meeting that can't go into Alder at its existing time, because Alder is too small "
     "for it or already in use, should be cancelled outright rather than moved elsewhere or retimed. Meetings "
     "on other days and in other rooms stay as they are.",
     [["get_calendar_info", {}], ["list_events", {"date": _WED, "room_id": "R-CEDAR"}],
      ["update_event", {"event_id": "E101", "changes": {"room_id": "R-ALDER"}}],
      ["update_event", {"event_id": "E102", "changes": {"room_id": "R-ALDER"}}],
      ["cancel_event", {"event_id": "E102"}],
      ["update_event", {"event_id": "E103", "changes": {"room_id": "R-ALDER"}}],
      ["cancel_event", {"event_id": "E103"}]],
     [["update_event", {"event_id": "E101", "changes": {"room_id": "R-ALDER"}}],
      ["update_event", {"event_id": "E102", "changes": {"room_id": "R-OAK"}}],
      ["cancel_event", {"event_id": "E103"}]],
     lambda s, i: _final(s, i, changes={"events": {
         "E101": {"room": "R-ALDER"}, "E102": None, "E103": None}}),
     ref_errors=[3, 5])

_add("T13", "calendar", "medium", _cal([
    ("Lena / Hiro 1:1", _TUE, "09:30", "10:00", "R-MAPLE", "U03", ["U09"]),
    ("Ops standup", _TUE, "10:00", "10:15", "R-ALDER", "U08", ["U03", "U09"]),
    ("Launch checklist", _TUE, "13:00", "14:00", "R-JUNIPER", "U01", ["U03", "U10"]),
    ("Design sync", _TUE, "11:00", "12:00", "R-MAPLE", "U04", ["U11", "U12"]),
    ("Launch retro", _WED, "13:00", "14:00", "R-JUNIPER", "U03", ["U01", "U10"])]),
     "Tomas Aguilar starts shadowing Lena Kowalczyk tomorrow, Tuesday. Add him as an attendee to every meeting "
     "Lena Kowalczyk is in on Tuesday, except one-to-ones (meetings that currently have exactly two attendees), "
     "which he should not join. Careful, there is another Lena in the company; her meetings are not involved. "
     "Meetings on other days stay as they are.",
     [["get_calendar_info", {}], ["find_people", {"query": "Lena"}], ["find_people", {"query": "Tomas"}],
      ["list_events", {"date": _TUE, "person_id": "U03"}],
      ["set_attendees", {"event_id": "E102", "add": ["U07"]}],
      ["set_attendees", {"event_id": "E103", "add": ["U07"]}]],
     [["set_attendees", {"event_id": "E101", "add": ["U07"]}],
      ["set_attendees", {"event_id": "E102", "add": ["U07"]}],
      ["set_attendees", {"event_id": "E103", "add": ["U07"]}]],
     lambda s, i: _final(s, i, changes={"events": {
         "E102": {"attendees": ["U03", "U07", "U08", "U09"]},
         "E103": {"attendees": ["U01", "U03", "U07", "U10"]}}}))

_add("T14", "calendar", "hard", _cal([
    ("Design crit", _THU, "10:00", "11:00", "R-ALDER", "U04", ["U11", "U12"]),
    ("All-hands prep", _THU, "10:00", "11:00", "R-MAPLE", "U08", ["U01", "U02", "U10"]),
    ("Design crit dry run", _WED, "10:00", "11:00", "R-ALDER", "U04", ["U11"])]),
     "On Thursday this week 'Design crit' and 'All-hands prep' run at the same time, and their organisers have "
     "agreed to swap rooms. Make it so each of the two meetings ends up in the room the other one has now. "
     "Times, attendees and titles must not change, and no other meeting should be touched; the Wednesday dry "
     "run keeps its room.",
     [["get_calendar_info", {}], ["list_events", {"date": _THU}],
      ["update_event", {"event_id": "E101", "changes": {"room_id": "R-MAPLE"}}],
      ["update_event", {"event_id": "E101", "changes": {"room_id": None}}],
      ["update_event", {"event_id": "E102", "changes": {"room_id": "R-ALDER"}}],
      ["update_event", {"event_id": "E101", "changes": {"room_id": "R-MAPLE"}}]],
     [["update_event", {"event_id": "E101", "changes": {"room_id": None}}],
      ["update_event", {"event_id": "E102", "changes": {"room_id": "R-ALDER"}}]],
     lambda s, i: _final(s, i, changes={"events": {
         "E101": {"room": "R-MAPLE"}, "E102": {"room": "R-ALDER"}}}),
     ref_errors=[2])

_add("T15", "calendar", "very hard", _cal([
    ("Infra review", _WED, "10:00", "11:00", "R-JUNIPER", "U02", ["U09", "U11"]),
    ("Cost walkthrough", _WED, "15:00", "16:00", "R-ALDER", "U02", ["U01"]),
    ("Ops standup", _WED, "09:00", "09:15", "R-MAPLE", "U08", ["U02", "U09"]),
    ("Recruiting debrief", _THU, "15:00", "16:00", "R-ALDER", "U05", ["U06"]),
    ("Infra review prep", _TUE, "16:00", "16:30", None, "U02", ["U09"])]),
     "Marek Dvorak is out all day this Wednesday. Go through every Wednesday meeting he is in. Where he is the "
     "organiser, move the meeting to Thursday at the same time, keeping the same room; if that room is already "
     "taken at that time on Thursday, still move it but with no room assigned. Where he is only an attendee, "
     "just remove him from the meeting and leave it where it is. His meetings on other days are unaffected.",
     [["get_calendar_info", {}], ["find_people", {"query": "Marek"}],
      ["list_events", {"date": _WED, "person_id": "U02"}],
      ["update_event", {"event_id": "E101", "changes": {"date": _THU}}],
      ["update_event", {"event_id": "E102", "changes": {"date": _THU}}],
      ["update_event", {"event_id": "E102", "changes": {"date": _THU, "room_id": None}}],
      ["set_attendees", {"event_id": "E103", "remove": ["U02"]}]],
     [["update_event", {"event_id": "E101", "changes": {"date": _THU}}],
      ["update_event", {"event_id": "E102", "changes": {"date": _THU, "room_id": "R-MAPLE"}}],
      ["set_attendees", {"event_id": "E103", "remove": ["U02"]}]],
     lambda s, i: _final(s, i, changes={"events": {
         "E101": {"date": _THU}, "E102": {"date": _THU, "room": None},
         "E103": {"attendees": ["U08", "U09"]}}}),
     ref_errors=[4])

_CAL16 = [("Quarterly planning", _FRI, "13:00", "16:00", "R-OAK", "U10", ["U01", "U02", "U08"]),
          ("Planning pre-read", _FRI, "11:00", "11:30", None, "U10", ["U01"])]

_add("T16", "calendar", "hard", _cal(_CAL16),
     "Friday's 'Quarterly planning' runs 13:00 to 16:00, which is too long in one go. Keep the existing meeting "
     "but make it end at 14:15. Then add a second meeting titled 'Quarterly planning part 2' that starts 30 "
     "minutes after the first one now ends and finishes at the original end time, with the same room, the same "
     "organiser and the same attendees. Nothing else on the calendar should change.",
     [["get_calendar_info", {}], ["list_events", {"date": _FRI}],
      ["update_event", {"event_id": "E101", "changes": {"end": "14:15"}}],
      ["create_event", {"title": "Quarterly planning part 2", "date": _FRI, "start": "14:45", "end": "16:00",
                        "organizer_id": "U10", "attendee_ids": ["U01", "U02", "U08"], "room_id": "R-OAK"}]],
     [["update_event", {"event_id": "E101", "changes": {"end": "14:15"}}],
      ["create_event", {"title": "Quarterly planning part 2", "date": _FRI, "start": "14:15", "end": "16:00",
                        "organizer_id": "U10", "attendee_ids": ["U01", "U02", "U08"], "room_id": "R-OAK"}]],
     lambda s, i: _final(s, i, changes={"events": {"E101": {"end": "14:15"}}}, new={"events": [{
         "title": _ti("Quarterly planning part 2"), "date": _FRI, "start": "14:45", "end": "16:00",
         "room": "R-OAK", "organizer": "U10", "attendees": ["U01", "U02", "U08", "U10"]}]}))


# --------------------------------------------------------------------------
# ticket fixtures + tasks T17-T24
# --------------------------------------------------------------------------
def _tk(title, status="open", priority="medium", assignee=None, labels=(), deps=(), est=1, sprint=None):
    return {"title": title, "status": status, "priority": priority, "assignee": assignee,
            "labels": sorted(labels), "depends_on": sorted(deps), "estimate": est, "sprint": sprint}


def _trk(tickets, on_leave=()):
    users = [("USR-1", "Rafael Ortiz", "engineer"), ("USR-2", "Noor Haddad", "engineer"),
             ("USR-3", "Imogen Hartley", "engineer"), ("USR-4", "Imogen Hale", "engineer"),
             ("USR-5", "Wendell Park", "lead"), ("USR-6", "Sunita Rao", "engineer")]
    return {
        "users": dict((u[0], {"name": u[1], "role": u[2], "on_leave": u[0] in on_leave}) for u in users),
        "labels": ["bug-api", "bug-ui", "checkout", "deferred", "frontend", "infra", "migration",
                   "security", "triage"],
        "sprints": {"SP-29": {"name": "Sprint 29", "capacity": 24, "state": "closed"},
                    "SP-30": {"name": "Sprint 30", "capacity": 30, "state": "active"},
                    "SP-31": {"name": "Sprint 31", "capacity": 20, "state": "planned"}},
        "tickets": dict(("TK-%d" % (201 + n), t) for n, t in enumerate(tickets)),
        "next_ticket": 201 + len(tickets),
    }


_add("T17", "tickets", "hard", _trk([
    _tk("Login page times out on SSO", "in_progress", "high", "USR-1", deps=["TK-203", "TK-204", "TK-205"], est=5),
    _tk("Login page times out on password reset", "open", "high", "USR-1", deps=["TK-206"], est=3),
    _tk("Raise SSO gateway timeout", "in_progress", "medium", "USR-2", est=2),
    _tk("Add SSO retry metric", "resolved", "low", "USR-2", est=1),
    _tk("Update IdP certificate", "open", "high", None, labels=["security"], est=1),
    _tk("Password reset email queue", "open", "medium", None, est=3)]),
     "The SSO login timeout ticket ('Login page times out on SSO') is fixed and should end up closed. The work "
     "in the tickets it depends on is done too: any of those that isn't already resolved or closed should be "
     "set to resolved (resolved, not closed), and any that is already resolved stays resolved. Don't touch the "
     "password-reset timeout ticket or anything else.",
     [["search_tickets", {"query": "Login page times out"}], ["get_ticket", {"ticket_id": "TK-201"}],
      ["search_tickets", {"query": "SSO"}],
      ["set_status", {"ticket_id": "TK-203", "status": "resolved"}],
      ["set_status", {"ticket_id": "TK-205", "status": "resolved"}],
      ["set_status", {"ticket_id": "TK-201", "status": "resolved"}],
      ["set_status", {"ticket_id": "TK-201", "status": "closed"}]],
     [["set_status", {"ticket_id": "TK-203", "status": "resolved"}],
      ["set_status", {"ticket_id": "TK-205", "status": "resolved"}],
      ["set_status", {"ticket_id": "TK-201", "status": "resolved"}]],
     lambda s, i: _final(s, i, changes={"tickets": {
         "TK-201": {"status": "closed"}, "TK-203": {"status": "resolved"}, "TK-205": {"status": "resolved"}}}))

_TRK18 = [
    _tk("Checkout button misaligned on mobile", "open", "medium", "USR-3", labels=["bug-ui"], est=2),
    _tk("Refactor cart totals", "in_progress", "medium", "USR-3", est=5),
    _tk("Patch token leak in audit log", "in_progress", "urgent", "USR-3", labels=["security"], est=3),
    _tk("Add address autocomplete", "open", "low", "USR-3", labels=["checkout"], est=5),
    _tk("Fix flaky cart test", "resolved", "low", "USR-3", est=1),
    _tk("Upgrade payment SDK", "blocked", "high", "USR-3", labels=["checkout"], est=8),
    _tk("Document cart API", "open", "low", "USR-4", est=2),
    _tk("Rotate signing keys", "open", "high", "USR-2", labels=["security"], est=3)]

_add("T18", "tickets", "hard", _trk(_TRK18, on_leave=["USR-3"]),
     "Imogen Hartley has gone on leave. Reassign her tickets that are open or in progress to Rafael Ortiz, "
     "except any of those carrying the security label, which go to Noor Haddad instead. Her tickets in any "
     "other status (blocked, resolved, closed) keep her as assignee. Note there's also an Imogen Hale on the "
     "team; her tickets are nothing to do with this.",
     [["list_users", {}], ["search_tickets", {"assignee_id": "USR-3"}],
      ["update_ticket", {"ticket_id": "TK-201", "fields": {"assignee_id": "USR-1"}}],
      ["update_ticket", {"ticket_id": "TK-202", "fields": {"assignee_id": "USR-1"}}],
      ["update_ticket", {"ticket_id": "TK-203", "fields": {"assignee_id": "USR-2"}}],
      ["update_ticket", {"ticket_id": "TK-204", "fields": {"assignee_id": "USR-1"}}]],
     [["update_ticket", {"ticket_id": "TK-201", "fields": {"assignee_id": "USR-1"}}],
      ["update_ticket", {"ticket_id": "TK-202", "fields": {"assignee_id": "USR-1"}}],
      ["update_ticket", {"ticket_id": "TK-203", "fields": {"assignee_id": "USR-2"}}],
      ["update_ticket", {"ticket_id": "TK-204", "fields": {"assignee_id": "USR-1"}}],
      ["update_ticket", {"ticket_id": "TK-206", "fields": {"assignee_id": "USR-1"}}]],
     lambda s, i: _final(s, i, changes={"tickets": {
         "TK-201": {"assignee": "USR-1"}, "TK-202": {"assignee": "USR-1"},
         "TK-203": {"assignee": "USR-2"}, "TK-204": {"assignee": "USR-1"}}}))

_add("T19", "tickets", "hard", _trk([
    _tk("Sprint 31 planning doc", "open", "medium", "USR-5", est=6, sprint="SP-31"),
    _tk("Search index rebuild", "open", "high", "USR-2", labels=["infra"], est=5, sprint="SP-31"),
    _tk("Checkout: save card toggle", "open", "high", "USR-1", labels=["checkout"], est=3),
    _tk("Checkout: guest email validation", "open", "medium", "USR-4", labels=["checkout"], est=5),
    _tk("Checkout: gift message field", "open", "low", None, labels=["checkout"], est=4),
    _tk("Checkout: tax rounding", "in_progress", "high", "USR-1", labels=["checkout"], est=2, sprint="SP-30"),
    _tk("Wishlist sharing", "open", "low", None, est=2)]),
     "Planning for Sprint 31: add the tickets labelled checkout that aren't in any sprint yet. First work out "
     "whether their estimates all fit within what's left of the sprint's capacity. If they do, add them all. If "
     "they don't, leave out only the one with the lowest priority (keep it out of any sprint and add the label "
     "deferred to it) and add the others. Checkout tickets already in a sprint stay where they are.",
     [["list_sprints", {}], ["search_tickets", {"label": "checkout"}],
      ["move_to_sprint", {"ticket_id": "TK-203", "sprint_id": "SP-31"}],
      ["move_to_sprint", {"ticket_id": "TK-204", "sprint_id": "SP-31"}],
      ["edit_labels", {"ticket_id": "TK-205", "add": ["deferred"]}]],
     [["move_to_sprint", {"ticket_id": "TK-203", "sprint_id": "SP-31"}],
      ["move_to_sprint", {"ticket_id": "TK-205", "sprint_id": "SP-31"}],
      ["edit_labels", {"ticket_id": "TK-204", "add": ["deferred"]}]],
     lambda s, i: _final(s, i, changes={"tickets": {
         "TK-203": {"sprint": "SP-31"}, "TK-204": {"sprint": "SP-31"},
         "TK-205": {"labels": ["checkout", "deferred"]}}}))


def _c20(s, i):
    fresh = dict((k, v) for k, v in s["tickets"].items() if k not in i["tickets"])
    a = [k for k, v in fresh.items() if _n(v["title"]) == _n("Billing DB: schema freeze")]
    b = [k for k, v in fresh.items() if _n(v["title"]) == _n("Billing DB: data backfill")]
    if len(fresh) != 2 or len(a) != 1 or len(b) != 1:
        return False
    a, b = a[0], b[0]
    common = {"status": "open", "priority": "high", "assignee": None, "labels": ["migration"], "sprint": None}
    return _final(s, i, changes={"tickets": {"TK-201": {"depends_on": sorted([a, b]), "estimate": 6}}},
                  new={"tickets": [dict(common, estimate=2, depends_on=[]),
                                   dict(common, estimate=5, depends_on=[a])]})


_add("T20", "tickets", "hard", _trk([
    _tk("Migrate billing DB", "open", "high", "USR-6", labels=["migration"], est=13),
    _tk("Migrate billing dashboards", "open", "medium", "USR-1", labels=["migration"], est=8)],
    on_leave=["USR-6"]),
     "'Migrate billing DB' is too big, so split it. Create two new tickets: 'Billing DB: schema freeze' with "
     "estimate 2 and 'Billing DB: data backfill' with estimate 5. Both get the original's priority and the "
     "label migration, and should be assigned to the original's assignee, unless that person is on leave, in "
     "which case leave both unassigned. The backfill ticket depends on the schema freeze ticket. The original "
     "must depend on both new tickets, and its estimate must be reduced by the sum of the two new estimates. "
     "Leave the billing dashboards ticket alone.",
     [["search_tickets", {"query": "billing"}], ["get_ticket", {"ticket_id": "TK-201"}], ["list_users", {}],
      ["create_ticket", {"title": "Billing DB: schema freeze", "priority": "high", "estimate": 2,
                         "labels": ["migration"]}],
      ["create_ticket", {"title": "Billing DB: data backfill", "priority": "high", "estimate": 5,
                         "labels": ["migration"], "depends_on": ["TK-203"]}],
      ["link_dependency", {"ticket_id": "TK-201", "depends_on_id": "TK-203", "action": "add"}],
      ["link_dependency", {"ticket_id": "TK-201", "depends_on_id": "TK-204", "action": "add"}],
      ["update_ticket", {"ticket_id": "TK-201", "fields": {"estimate": 6}}]],
     [["create_ticket", {"title": "Billing DB: schema freeze", "priority": "high", "estimate": 2,
                         "labels": ["migration"]}],
      ["create_ticket", {"title": "Billing DB: data backfill", "priority": "high", "estimate": 5,
                         "labels": ["migration"], "depends_on": ["TK-203"]}],
      ["link_dependency", {"ticket_id": "TK-201", "depends_on_id": "TK-203", "action": "add"}],
      ["link_dependency", {"ticket_id": "TK-201", "depends_on_id": "TK-204", "action": "add"}]],
     _c20)

_add("T21", "tickets", "medium", _trk([
    _tk("Tooltip clipped in sidebar", "open", "low", None, labels=["bug-ui", "checkout"], est=1),
    _tk("Modal focus trap broken", "in_progress", "high", "USR-1", labels=["bug-ui", "frontend"], est=3),
    _tk("Dark mode contrast on badges", "closed", "low", "USR-4", labels=["bug-ui"], est=1),
    _tk("500 on empty cart API", "open", "urgent", "USR-2", labels=["bug-api"], est=2),
    _tk("Date picker off by one", "resolved", "medium", "USR-4", labels=["bug-ui"], est=2)]),
     "We're retiring the bug-ui label. On every ticket that has it, remove bug-ui and make sure the ticket has "
     "the frontend label instead (no duplicates if it's already there). The exception is tickets whose status "
     "is closed: leave those exactly as they are, old label included. Other labels on the tickets must be kept.",
     [["search_tickets", {"label": "bug-ui"}],
      ["edit_labels", {"ticket_id": "TK-201", "add": ["frontend"], "remove": ["bug-ui"]}],
      ["edit_labels", {"ticket_id": "TK-202", "add": ["frontend"], "remove": ["bug-ui"]}],
      ["edit_labels", {"ticket_id": "TK-205", "add": ["frontend"], "remove": ["bug-ui"]}]],
     [["edit_labels", {"ticket_id": "TK-201", "add": ["frontend"], "remove": ["bug-ui"]}],
      ["edit_labels", {"ticket_id": "TK-202", "add": ["frontend"], "remove": ["bug-ui"]}],
      ["edit_labels", {"ticket_id": "TK-203", "add": ["frontend"], "remove": ["bug-ui"]}],
      ["edit_labels", {"ticket_id": "TK-205", "add": ["frontend"], "remove": ["bug-ui"]}]],
     lambda s, i: _final(s, i, changes={"tickets": {
         "TK-201": {"labels": ["checkout", "frontend"]}, "TK-202": {"labels": ["frontend"]},
         "TK-205": {"labels": ["frontend"]}}}))

_add("T22", "tickets", "medium", _trk([
    _tk("Deploy pipeline v2", "in_progress", "high", "USR-1", labels=["infra"], est=8),
    _tk("Rotate CI secrets", "open", "high", "USR-2", labels=["infra", "security"], deps=["TK-201"], est=2),
    _tk("Deploy pipeline v2 docs", "open", "low", None, est=2)]),
     "'Deploy pipeline v2' (the pipeline ticket itself, not its docs ticket) must depend on 'Rotate CI "
     "secrets'. If the tracker refuses because that would be circular, then the existing dependency pointing "
     "the opposite way is the mistake: remove that one and add the correct one. Finally set 'Deploy pipeline "
     "v2' to blocked. Don't change the status of any other ticket.",
     [["search_tickets", {"query": "Deploy pipeline"}], ["search_tickets", {"query": "Rotate CI"}],
      ["link_dependency", {"ticket_id": "TK-201", "depends_on_id": "TK-202", "action": "add"}],
      ["link_dependency", {"ticket_id": "TK-202", "depends_on_id": "TK-201", "action": "remove"}],
      ["link_dependency", {"ticket_id": "TK-201", "depends_on_id": "TK-202", "action": "add"}],
      ["set_status", {"ticket_id": "TK-201", "status": "blocked"}]],
     [["link_dependency", {"ticket_id": "TK-203", "depends_on_id": "TK-202", "action": "add"}],
      ["set_status", {"ticket_id": "TK-203", "status": "blocked"}]],
     lambda s, i: _final(s, i, changes={"tickets": {
         "TK-201": {"depends_on": ["TK-202"], "status": "blocked"}, "TK-202": {"depends_on": []}}}),
     ref_errors=[2])

_add("T23", "tickets", "hard", _trk([
    _tk("Webhook retries drop payload", "open", "high", None, labels=["bug-api"], est=3),
    _tk("Refund endpoint returns 200 on failure", "open", "urgent", None, labels=["bug-api"], est=2),
    _tk("Rate limiter config drift", "open", "high", "USR-1", labels=["infra"], est=2),
    _tk("Stale cache after price change", "blocked", "high", None, est=5),
    _tk("Footer links wrap on tablet", "open", "medium", None, labels=["bug-ui"], est=1),
    _tk("Order export truncates at 10k rows", "open", "urgent", None, est=3),
    _tk("Session cookie missing SameSite", "resolved", "high", None, labels=["security"], est=1),
    _tk("Coupon stacking allows negative total", "open", "high", None, labels=["checkout"], est=5),
    _tk("Address form loses state on back", "in_progress", "urgent", "USR-2", labels=["checkout"], est=3),
    _tk("Typo in onboarding email", "open", "low", None, est=1),
    _tk("Invoice PDF renders blank for RTL", "open", "high", None, labels=["bug-ui"], est=3)]),
     "I need a triage number. Count the tickets that are in status open (exactly open, not in progress, blocked "
     "or anything else), have priority high or urgent, and have no assignee. Then create one ticket titled "
     "'Triage backlog' with priority medium, the label triage, assigned to whoever is the team lead, and with "
     "its estimate set to the count you found. Don't modify any existing ticket.",
     [["search_tickets", {"status": "open"}], ["list_users", {}],
      ["create_ticket", {"title": "Triage backlog", "priority": "medium", "estimate": 5, "labels": ["triage"],
                         "assignee_id": "USR-5"}]],
     [["create_ticket", {"title": "Triage backlog", "priority": "medium", "estimate": 6, "labels": ["triage"],
                         "assignee_id": "USR-5"}]],
     lambda s, i: _final(s, i, new={"tickets": [{
         "title": _ti("Triage backlog"), "status": "open", "priority": "medium", "assignee": "USR-5",
         "labels": ["triage"], "depends_on": [], "estimate": 5, "sprint": None}]}))

_add("T24", "tickets", "very hard", _trk([
    _tk("Export invoices as CSV", "resolved", "medium", "USR-1", est=3, sprint="SP-30"),
    _tk("Bulk refund tool", "in_progress", "high", "USR-2", est=5, sprint="SP-30"),
    _tk("Ledger reconciliation job", "open", "high", None, est=8, sprint="SP-30"),
    _tk("Tax ID validation", "blocked", "medium", "USR-4", est=3, sprint="SP-30"),
    _tk("Invoice footer typo", "closed", "low", "USR-4", est=1, sprint="SP-30"),
    _tk("Statement PDF redesign", "open", "medium", "USR-1", est=7, sprint="SP-31"),
    _tk("Dunning email copy", "open", "low", None, est=5, sprint="SP-31"),
    _tk("Currency switcher", "open", "medium", None, est=4)]),
     "Sprint 30 is ending. Go through its tickets in ascending ticket-id order. A resolved ticket gets closed "
     "and stays in Sprint 30. A ticket that is open, in progress or blocked moves to Sprint 31, but if Sprint "
     "31 doesn't have enough capacity left for it at that point, take it out of any sprint instead and add the "
     "label deferred to it. Tickets that are already closed are left alone, as is everything outside Sprint 30.",
     [["list_sprints", {}], ["search_tickets", {"sprint_id": "SP-30"}],
      ["set_status", {"ticket_id": "TK-201", "status": "closed"}],
      ["move_to_sprint", {"ticket_id": "TK-202", "sprint_id": "SP-31"}],
      ["move_to_sprint", {"ticket_id": "TK-203", "sprint_id": "SP-31"}],
      ["move_to_sprint", {"ticket_id": "TK-203", "sprint_id": None}],
      ["edit_labels", {"ticket_id": "TK-203", "add": ["deferred"]}],
      ["move_to_sprint", {"ticket_id": "TK-204", "sprint_id": "SP-31"}]],
     [["set_status", {"ticket_id": "TK-201", "status": "closed"}],
      ["move_to_sprint", {"ticket_id": "TK-203", "sprint_id": "SP-31"}],
      ["move_to_sprint", {"ticket_id": "TK-202", "sprint_id": None}],
      ["edit_labels", {"ticket_id": "TK-202", "add": ["deferred"]}],
      ["move_to_sprint", {"ticket_id": "TK-204", "sprint_id": None}],
      ["edit_labels", {"ticket_id": "TK-204", "add": ["deferred"]}]],
     lambda s, i: _final(s, i, changes={"tickets": {
         "TK-201": {"status": "closed"}, "TK-202": {"sprint": "SP-31"},
         "TK-203": {"sprint": None, "labels": ["deferred"]}, "TK-204": {"sprint": "SP-31"}}}),
     ref_errors=[4])


# --------------------------------------------------------------------------
# file-tree fixtures + tasks T25-T32
# --------------------------------------------------------------------------
def _fs(files, extra_folders=()):
    folders = set(["/"]) | set(extra_folders)
    out = {}
    for path, (size, modified, tags, locked) in files.items():
        out[path] = {"size_mb": size, "modified": modified, "tags": sorted(tags), "locked": locked}
        p = _parent(path)
        while p != "/":
            folders.add(p)
            p = _parent(p)
    for f in list(folders):
        p = f
        while p != "/":
            folders.add(p)
            p = _parent(p)
    return {"today": "2026-03-20", "folders": sorted(folders), "files": out, "trash": []}


def _mv(files, a, b):
    files[b] = files.pop(a)


def _m25(files, folders):
    folders.add("/reports/2026")
    for n in ("scan_0312.pdf", "invoice_771.pdf", "q1_forecast.pdf"):
        _mv(files, "/inbox/" + n, "/reports/2026/" + n)


_add("T25", "files", "medium", _fs({
    "/inbox/scan_0312.pdf": (2, "2026-03-12", [], False),
    "/inbox/invoice_771.pdf": (1, "2026-03-14", ["review"], False),
    "/inbox/minutes.docx": (1, "2026-03-15", ["draft"], False),
    "/inbox/photo.jpg": (6, "2026-03-16", [], False),
    "/inbox/q1_forecast.pdf": (3, "2026-03-18", ["draft"], False),
    "/inbox/old/legacy.pdf": (4, "2024-07-01", ["archive"], False),
    "/reports/2025/annual.pdf": (9, "2026-01-20", ["final"], True)}),
     "Please file the PDFs from the inbox: every .pdf file sitting directly in /inbox (not in its subfolders) "
     "should be moved into /reports/2026, keeping its name. If that folder doesn't exist yet, create it. Files "
     "of other types stay in /inbox and nothing in the subfolders of /inbox should move.",
     [["list_folder", {"path": "/inbox"}], ["list_folder", {"path": "/reports"}],
      ["create_folder", {"path": "/reports/2026"}],
      ["move", {"src": "/inbox/scan_0312.pdf", "dest_folder": "/reports/2026"}],
      ["move", {"src": "/inbox/invoice_771.pdf", "dest_folder": "/reports/2026"}],
      ["move", {"src": "/inbox/q1_forecast.pdf", "dest_folder": "/reports/2026"}]],
     [["create_folder", {"path": "/reports/2026"}],
      ["move", {"src": "/inbox/scan_0312.pdf", "dest_folder": "/reports/2026"}],
      ["move", {"src": "/inbox/invoice_771.pdf", "dest_folder": "/reports/2026"}],
      ["move", {"src": "/inbox/q1_forecast.pdf", "dest_folder": "/reports/2026"}],
      ["move", {"src": "/inbox/old/legacy.pdf", "dest_folder": "/reports/2026"}]],
     lambda s, i: _fs_check(s, i, _m25))


def _m26(files, folders):
    _mv(files, "/projects/atlas/notes.txt", "/projects/atlas/notes_old.txt")
    _mv(files, "/projects/atlas/notes_v2.txt", "/projects/atlas/notes.txt")
    files["/projects/atlas/notes.txt"]["tags"] = ["final"]


_add("T26", "files", "hard", _fs({
    "/projects/atlas/notes.txt": (1, "2026-01-10", ["final"], False),
    "/projects/atlas/notes_v2.txt": (1, "2026-03-11", ["draft"], False),
    "/projects/atlas/plan.xlsx": (2, "2026-02-02", [], False),
    "/projects/atlas-archive/notes.txt": (1, "2025-06-01", ["archive"], False),
    "/projects/atlas-archive/notes_v2.txt": (1, "2025-08-19", ["archive", "draft"], False)}),
     "In /projects/atlas, notes_v2.txt should become the main notes file. Rename it to notes.txt. The file "
     "currently called notes.txt must not be lost: it should end up in the same folder as notes_old.txt with "
     "its tags unchanged. The new notes.txt should end up tagged final and no longer tagged draft. The "
     "similarly named files in /projects/atlas-archive must stay exactly as they are.",
     [["list_folder", {"path": "/projects/atlas"}],
      ["rename", {"path": "/projects/atlas/notes_v2.txt", "new_name": "notes.txt"}],
      ["rename", {"path": "/projects/atlas/notes.txt", "new_name": "notes_old.txt"}],
      ["rename", {"path": "/projects/atlas/notes_v2.txt", "new_name": "notes.txt"}],
      ["set_tags", {"path": "/projects/atlas/notes.txt", "add": ["final"], "remove": ["draft"]}]],
     [["rename", {"path": "/projects/atlas-archive/notes.txt", "new_name": "notes_old.txt"}],
      ["rename", {"path": "/projects/atlas-archive/notes_v2.txt", "new_name": "notes.txt"}],
      ["set_tags", {"path": "/projects/atlas-archive/notes.txt", "add": ["final"], "remove": ["draft"]}]],
     lambda s, i: _fs_check(s, i, _m26), ref_errors=[1])


def _m27(files, folders):
    del files["/tmp/scratch-old/build.log"]
    del files["/tmp/scratch-old/core.dump"]
    folders.discard("/tmp/scratch-old")


_add("T27", "files", "hard", _fs({
    "/tmp/scratch-old/build.log": (3, "2025-11-30", [], False),
    "/tmp/scratch-old/core.dump": (512, "2025-11-30", [], True),
    "/tmp/scratch/build.log": (2, "2026-03-19", [], False),
    "/tmp/scratch/core.dump": (480, "2026-03-19", [], True),
    "/tmp/readme.txt": (1, "2025-01-05", [], False)}),
     "Please get rid of the folder /tmp/scratch-old completely: the folder itself and every file in it should "
     "be deleted. If something in there is locked, unlock it so it can be deleted. Be careful not to touch "
     "/tmp/scratch, which is a different folder that's still in use, or anything else under /tmp.",
     [["list_folder", {"path": "/tmp/scratch-old"}],
      ["delete", {"path": "/tmp/scratch-old/build.log"}],
      ["delete", {"path": "/tmp/scratch-old/core.dump"}],
      ["set_lock", {"path": "/tmp/scratch-old/core.dump", "locked": False}],
      ["delete", {"path": "/tmp/scratch-old/core.dump"}],
      ["delete", {"path": "/tmp/scratch-old"}]],
     [["delete", {"path": "/tmp/scratch-old/build.log"}],
      ["delete", {"path": "/tmp/scratch-old/core.dump"}],
      ["delete", {"path": "/tmp/scratch-old"}]],
     lambda s, i: _fs_check(s, i, _m27), ref_errors=[2])


def _m28(files, folders):
    files["/media/raw/a_interview.mov"]["tags"] = ["archive"]
    files["/media/raw/b_broll.mov"]["tags"] = ["archive", "review"]
    _mv(files, "/media/raw/a_interview.mov", "/media/large/a_interview.mov")
    _mv(files, "/media/raw/d_keynote.mov", "/media/large/d_keynote.mov")


_add("T28", "files", "medium", _fs({
    "/media/raw/a_interview.mov": (820, "2025-11-02", [], False),
    "/media/raw/b_broll.mov": (300, "2025-12-30", ["review"], False),
    "/media/raw/c_teaser.mov": (500, "2026-01-01", [], False),
    "/media/raw/d_keynote.mov": (1210, "2026-02-11", [], False),
    "/media/raw/e_voiceover.wav": (45, "2026-03-01", [], False),
    "/media/large/old_master.mov": (2300, "2025-05-05", ["archive"], False)}),
     "Tidy /media/raw for me. Every file there that is bigger than 500 MB should be moved to /media/large (same "
     "name). Separately, every file that was in /media/raw and was last modified before 2026-01-01 should get "
     "the archive tag, whether or not it was moved. A file of exactly 500 MB is not bigger than 500, and one "
     "modified on 2026-01-01 is not before it. Existing tags stay.",
     [["list_folder", {"path": "/media/raw"}],
      ["set_tags", {"path": "/media/raw/a_interview.mov", "add": ["archive"]}],
      ["set_tags", {"path": "/media/raw/b_broll.mov", "add": ["archive"]}],
      ["move", {"src": "/media/raw/a_interview.mov", "dest_folder": "/media/large"}],
      ["move", {"src": "/media/raw/d_keynote.mov", "dest_folder": "/media/large"}]],
     [["set_tags", {"path": "/media/raw/a_interview.mov", "add": ["archive"]}],
      ["set_tags", {"path": "/media/raw/b_broll.mov", "add": ["archive"]}],
      ["move", {"src": "/media/raw/a_interview.mov", "dest_folder": "/media/large"}],
      ["move", {"src": "/media/raw/d_keynote.mov", "dest_folder": "/media/large"}],
      ["move", {"src": "/media/raw/c_teaser.mov", "dest_folder": "/media/large"}]],
     lambda s, i: _fs_check(s, i, _m28))


def _m29(files, folders):
    folders.add("/contracts/pending")
    _mv(files, "/contracts/acme_msa.pdf", "/contracts/signed/acme_msa.pdf")
    _mv(files, "/contracts/borel_nda.pdf", "/contracts/signed/borel_nda_dup.pdf")
    _mv(files, "/contracts/corvid_sow.pdf", "/contracts/pending/corvid_sow.pdf")


_add("T29", "files", "very hard", _fs({
    "/contracts/acme_msa.pdf": (2, "2026-02-01", ["final"], False),
    "/contracts/borel_nda.pdf": (1, "2026-03-02", ["final"], False),
    "/contracts/corvid_sow.pdf": (1, "2026-03-10", ["draft", "review"], False),
    "/contracts/delta_terms.pdf": (1, "2026-03-12", [], False),
    "/contracts/eagle_lease.pdf": (3, "2026-03-15", ["review"], False),
    "/contracts/signed/borel_nda.pdf": (1, "2025-03-02", ["archive", "final"], False),
    "/contracts/signed/zephyr_msa.pdf": (2, "2025-09-09", ["final"], False)}),
     "Sort the files that sit directly in /contracts. Anything tagged final goes to /contracts/signed; anything "
     "tagged draft goes to /contracts/pending (create whichever of those folders is missing). Files with "
     "neither tag stay put. If the destination already has a file with the same name, keep both: give the "
     "incoming file a _dup suffix before its extension, e.g. x.pdf becomes x_dup.pdf, and leave the existing "
     "file alone.",
     [["list_folder", {"path": "/contracts"}],
      ["move", {"src": "/contracts/acme_msa.pdf", "dest_folder": "/contracts/signed"}],
      ["move", {"src": "/contracts/borel_nda.pdf", "dest_folder": "/contracts/signed"}],
      ["move", {"src": "/contracts/borel_nda.pdf", "dest_folder": "/contracts/signed",
                "new_name": "borel_nda_dup.pdf"}],
      ["move", {"src": "/contracts/corvid_sow.pdf", "dest_folder": "/contracts/pending"}],
      ["create_folder", {"path": "/contracts/pending"}],
      ["move", {"src": "/contracts/corvid_sow.pdf", "dest_folder": "/contracts/pending"}]],
     [["move", {"src": "/contracts/acme_msa.pdf", "dest_folder": "/contracts/signed"}],
      ["create_folder", {"path": "/contracts/pending"}],
      ["move", {"src": "/contracts/corvid_sow.pdf", "dest_folder": "/contracts/pending"}],
      ["move", {"src": "/contracts/eagle_lease.pdf", "dest_folder": "/contracts/pending"}],
      ["move", {"src": "/contracts/borel_nda.pdf", "dest_folder": "/contracts/signed",
                "new_name": "borel_nda_dup.pdf"}]],
     lambda s, i: _fs_check(s, i, _m29), ref_errors=[2, 4])


def _m30(files, folders):
    for p in ("/hr/salary_bands.xlsx", "/hr/2025/salary_review.docx", "/hr/payroll/Salary_notes.txt"):
        files[p]["tags"] = sorted(set(files[p]["tags"]) | set(["confidential"]))
        files[p]["locked"] = True


_add("T30", "files", "hard", _fs({
    "/hr/salary_bands.xlsx": (1, "2026-01-15", ["final"], False),
    "/hr/2025/salary_review.docx": (1, "2025-12-01", ["review"], False),
    "/hr/2025/offsite_agenda.docx": (1, "2025-09-09", [], False),
    "/hr/payroll/Salary_notes.txt": (1, "2026-02-20", [], False),
    "/hr/payroll/bonus_pool.xlsx": (1, "2026-02-21", ["draft"], False),
    "/hr-archive/salary_2023.xlsx": (1, "2023-12-31", ["archive"], False)}),
     "Lock down salary documents. Every file anywhere under /hr, including its subfolders, whose name contains "
     "'salary' (capital letters or not) should get the confidential tag added and be locked. Keep whatever tags "
     "they already have. The folder /hr-archive is a separate tree and nothing in it should be changed, and "
     "other /hr files stay as they are.",
     [["search_files", {"name_contains": "salary", "under": "/hr"}],
      ["set_tags", {"path": "/hr/salary_bands.xlsx", "add": ["confidential"]}],
      ["set_lock", {"path": "/hr/salary_bands.xlsx", "locked": True}],
      ["set_tags", {"path": "/hr/2025/salary_review.docx", "add": ["confidential"]}],
      ["set_lock", {"path": "/hr/2025/salary_review.docx", "locked": True}],
      ["set_tags", {"path": "/hr/payroll/Salary_notes.txt", "add": ["confidential"]}],
      ["set_lock", {"path": "/hr/payroll/Salary_notes.txt", "locked": True}]],
     [["set_tags", {"path": "/hr/salary_bands.xlsx", "add": ["confidential"]}],
      ["set_lock", {"path": "/hr/salary_bands.xlsx", "locked": True}],
      ["set_tags", {"path": "/hr/2025/salary_review.docx", "add": ["confidential"]}],
      ["set_lock", {"path": "/hr/2025/salary_review.docx", "locked": True}],
      ["set_tags", {"path": "/hr/payroll/Salary_notes.txt", "add": ["confidential"]}],
      ["set_lock", {"path": "/hr/payroll/Salary_notes.txt", "locked": True}],
      ["set_tags", {"path": "/hr-archive/salary_2023.xlsx", "add": ["confidential"]}],
      ["set_lock", {"path": "/hr-archive/salary_2023.xlsx", "locked": True}]],
     lambda s, i: _fs_check(s, i, _m30))


def _m31(files, folders):
    v3 = "/proposals/harbor/proposal_v3.docx"
    files["/proposals/harbor/proposal_v4.docx"] = dict(files[v3], tags=["draft"], locked=False)
    files[v3]["tags"] = ["final", "review"]


_add("T31", "files", "hard", _fs({
    "/proposals/harbor/proposal_v1.docx": (2, "2026-01-08", ["archive"], False),
    "/proposals/harbor/proposal_v2.docx": (2, "2026-02-03", ["archive"], False),
    "/proposals/harbor/proposal_v3.docx": (3, "2026-03-04", ["draft", "review"], False),
    "/proposals/harbor/budget.xlsx": (1, "2026-03-04", [], False),
    "/proposals/harbour/proposal_v5.docx": (4, "2026-03-17", ["draft"], False)}),
     "In /proposals/harbor (spelled without a 'u'; /proposals/harbour is another client) the proposal files "
     "are numbered proposal_v1.docx, proposal_v2.docx and so on. Copy the highest-numbered one to a new file "
     "in the same folder named with the next version number. The new copy should carry the draft tag and no "
     "other tags. The file it was copied from should have its draft tag replaced by final, keeping its other "
     "tags.",
     [["list_folder", {"path": "/proposals/harbor"}],
      ["copy_file", {"src": "/proposals/harbor/proposal_v3.docx", "dest_folder": "/proposals/harbor",
                     "new_name": "proposal_v4.docx"}],
      ["set_tags", {"path": "/proposals/harbor/proposal_v4.docx", "remove": ["review"]}],
      ["set_tags", {"path": "/proposals/harbor/proposal_v3.docx", "add": ["final"], "remove": ["draft"]}]],
     [["copy_file", {"src": "/proposals/harbor/proposal_v3.docx", "dest_folder": "/proposals/harbor",
                     "new_name": "proposal_v4.docx"}],
      ["set_tags", {"path": "/proposals/harbor/proposal_v3.docx", "add": ["final"], "remove": ["draft"]}]],
     lambda s, i: _fs_check(s, i, _m31, loose=["/proposals/harbor/proposal_v4.docx"]))


def _m32(files, folders):
    _mv(files, "/shared/q1/jan/summary.csv", "/shared/q1/jan_summary.csv")
    _mv(files, "/shared/q1/feb/summary.csv", "/shared/q1/feb_summary.csv")
    folders.discard("/shared/q1/jan")
    folders.discard("/shared/q1/feb")


_add("T32", "files", "hard", _fs({
    "/shared/q1/jan/summary.csv": (1, "2026-02-01", ["final"], False),
    "/shared/q1/feb/summary.csv": (1, "2026-03-01", ["final"], True),
    "/shared/q1/readme.txt": (1, "2026-01-02", [], False),
    "/shared/q2/apr/summary.csv": (1, "2026-03-19", ["draft"], False)}),
     "Flatten /shared/q1: it has month subfolders with files in them. Move each of those files up into "
     "/shared/q1 itself, renamed with the month folder's name and an underscore in front (so jan/summary.csv "
     "becomes jan_summary.csv), then delete the emptied month subfolders. A file that is locked must still be "
     "moved and must be locked again at the end. Files already directly in /shared/q1, and everything in "
     "/shared/q2, are not to be changed.",
     [["search_files", {"under": "/shared/q1"}],
      ["move", {"src": "/shared/q1/jan/summary.csv", "dest_folder": "/shared/q1", "new_name": "jan_summary.csv"}],
      ["move", {"src": "/shared/q1/feb/summary.csv", "dest_folder": "/shared/q1", "new_name": "feb_summary.csv"}],
      ["set_lock", {"path": "/shared/q1/feb/summary.csv", "locked": False}],
      ["move", {"src": "/shared/q1/feb/summary.csv", "dest_folder": "/shared/q1", "new_name": "feb_summary.csv"}],
      ["set_lock", {"path": "/shared/q1/feb_summary.csv", "locked": True}],
      ["delete", {"path": "/shared/q1/jan"}], ["delete", {"path": "/shared/q1/feb"}]],
     [["move", {"src": "/shared/q1/jan/summary.csv", "dest_folder": "/shared/q1", "new_name": "jan_summary.csv"}],
      ["set_lock", {"path": "/shared/q1/feb/summary.csv", "locked": False}],
      ["move", {"src": "/shared/q1/feb/summary.csv", "dest_folder": "/shared/q1", "new_name": "feb_summary.csv"}],
      ["delete", {"path": "/shared/q1/jan"}], ["delete", {"path": "/shared/q1/feb"}]],
     lambda s, i: _fs_check(s, i, _m32), ref_errors=[2])


# --------------------------------------------------------------------------
# clinic fixtures + tasks T33-T40
# --------------------------------------------------------------------------
def _clinic(appts, waitlist=(), flags=None):
    gp = ["checkup", "follow_up", "consult"]
    week = ["mon", "tue", "wed", "thu", "fri"]
    patients = [("P01", "Maria Okafor", "1987-03-02"), ("P02", "Maria Okafor", "1962-11-19"),
                ("P03", "Tobias Reinholt", "1979-06-30"), ("P04", "Helen Marsh", "1955-01-12"),
                ("P05", "Helen March", "1991-08-08"), ("P06", "Arjun Mehta", "2001-04-17"),
                ("P07", "Grace Oyelaran", "1984-10-05"), ("P08", "Samuel Petrov", "1970-02-23"),
                ("P09", "Lucia Ferrand", "1996-12-01"), ("P10", "Owen Blackwood", "1968-07-14"),
                ("P11", "Yara Haddad", "1989-05-27"), ("P12", "Felix Brandt", "1975-09-09"),
                ("P13", "Felicia Brandt", "2003-03-03")]
    flags = flags or {}
    st = {
        "today": "2026-05-18",
        "hours": {"open": "08:00", "close": "17:00"},
        "durations": {"checkup": 30, "follow_up": 15, "vaccination": 15, "consult": 45},
        "clinicians": {
            "C1": {"name": "Dr. Ingrid Lindqvist", "works": ["wed", "thu", "fri"], "services": gp},
            "C2": {"name": "Dr. Ngozi Abara", "works": ["mon", "tue", "wed", "thu"], "services": gp},
            "C3": {"name": "Dr. Wei Chen", "works": week, "services": gp},
            "C4": {"name": "Nurse Paulo Reyes", "works": ["mon", "tue", "thu"],
                   "services": ["vaccination", "follow_up"]},
            "C5": {"name": "Dr. Ingrid Lindahl", "works": week, "services": gp},
        },
        "patients": dict((p[0], {"name": p[1], "dob": p[2], "phone": "555-01%02d" % (n + 1),
                                 "flags": sorted(flags.get(p[0], []))}) for n, p in enumerate(patients)),
        "appointments": {},
        "waitlist": [{"patient": w[0], "clinician": w[1], "type": w[2]} for w in waitlist],
        "next_appt": 501 + len(appts),
    }
    for n, a in enumerate(appts):
        status = a[5] if len(a) > 5 else "booked"
        st["appointments"]["A%d" % (501 + n)] = {
            "patient": a[0], "clinician": a[1], "date": a[2], "time": a[3], "type": a[4], "status": status,
            "cancel_reason": "patient_request" if status == "cancelled" else None}
    return st


_add("T33", "clinic", "hard", _clinic([
    ("P06", "C1", "2026-05-20", "09:15", "checkup"),
    ("P07", "C1", "2026-05-20", "10:00", "consult"),
    ("P02", "C1", "2026-05-20", "09:00", "follow_up"),
    ("P09", "C5", "2026-05-19", "09:30", "checkup")]),
     "Book a follow-up for Maria Okafor (the one born in 1987; there are two patients with that name) with "
     "Dr. Lindqvist on Dr. Lindqvist's first working day after today. She'd like 09:30; if Dr. Lindqvist isn't "
     "free for the whole appointment then, take the earliest later start time that same day at which it fits. "
     "Just the one booking, nothing else.",
     [["get_clinic_info", {}], ["find_patients", {"query": "Maria Okafor"}],
      ["list_appointments", {"clinician_id": "C1", "date": "2026-05-20"}],
      ["book_appointment", {"patient_id": "P01", "clinician_id": "C1", "date": "2026-05-20", "time": "09:30",
                            "type": "follow_up"}],
      ["book_appointment", {"patient_id": "P01", "clinician_id": "C1", "date": "2026-05-20", "time": "09:45",
                            "type": "follow_up"}]],
     [["book_appointment", {"patient_id": "P02", "clinician_id": "C1", "date": "2026-05-20", "time": "09:45",
                            "type": "follow_up"}]],
     lambda s, i: _final(s, i, new={"appointments": [{
         "patient": "P01", "clinician": "C1", "date": "2026-05-20", "time": "09:45", "type": "follow_up",
         "status": "booked"}]}),
     ref_errors=[3])

_add("T34", "clinic", "very hard", _clinic([
    ("P06", "C2", "2026-05-19", "09:00", "checkup"),
    ("P07", "C2", "2026-05-19", "10:30", "consult"),
    ("P08", "C2", "2026-05-19", "14:00", "follow_up"),
    ("P09", "C2", "2026-05-19", "11:30", "checkup", "cancelled"),
    ("P10", "C3", "2026-05-19", "11:00", "checkup"),
    ("P11", "C2", "2026-05-20", "09:00", "checkup"),
    ("P12", "C3", "2026-05-19", "15:00", "consult")], waitlist=[("P13", "C2", "checkup")]),
     "Dr. Abara is off sick tomorrow. For each appointment she has booked for tomorrow: move it to Dr. Chen at "
     "the same time on the same day if Dr. Chen is free for it; if Dr. Chen is not free, cancel it with reason "
     "clinician_unavailable and put that patient on Dr. Abara's waitlist for the same appointment type. "
     "Appointments already cancelled, and her appointments on other days, are not to be touched.",
     [["get_clinic_info", {}], ["list_appointments", {"clinician_id": "C2", "date": "2026-05-19"}],
      ["reschedule_appointment", {"appointment_id": "A501", "new": {"clinician_id": "C3"}}],
      ["reschedule_appointment", {"appointment_id": "A502", "new": {"clinician_id": "C3"}}],
      ["cancel_appointment", {"appointment_id": "A502", "reason": "clinician_unavailable"}],
      ["manage_waitlist", {"action": "add", "patient_id": "P07", "clinician_id": "C2", "type": "consult"}],
      ["reschedule_appointment", {"appointment_id": "A503", "new": {"clinician_id": "C3"}}]],
     [["reschedule_appointment", {"appointment_id": "A501", "new": {"clinician_id": "C3"}}],
      ["reschedule_appointment", {"appointment_id": "A502", "new": {"clinician_id": "C3", "time": "11:30"}}],
      ["reschedule_appointment", {"appointment_id": "A503", "new": {"clinician_id": "C3"}}]],
     lambda s, i: _final(s, i, changes={
         "appointments": {"A501": {"clinician": "C3"}, "A503": {"clinician": "C3"},
                          "A502": {"status": "cancelled", "cancel_reason": "clinician_unavailable"}},
         "waitlist": i["waitlist"] + [{"patient": "P07", "clinician": "C2", "type": "consult"}]}),
     ref_errors=[3])

_add("T35", "clinic", "hard", _clinic([
    ("P09", "C3", "2026-05-18", "08:30", "checkup"),
    ("P10", "C3", "2026-05-18", "09:15", "follow_up"),
    ("P11", "C3", "2026-05-18", "10:00", "consult"),
    ("P12", "C3", "2026-05-18", "11:15", "checkup"),
    ("P06", "C3", "2026-05-18", "09:45", "follow_up", "cancelled"),
    ("P03", "C3", "2026-05-18", "13:00", "checkup"),
    ("P04", "C3", "2026-05-18", "15:00", "consult"),
    ("P05", "C5", "2026-05-18", "09:00", "checkup"),
    ("P13", "C3", "2026-05-18", "12:00", "follow_up")], flags={"P12": ["vip"]}),
     "Close out this morning for Dr. Chen. Of today's booked appointments with Dr. Chen that started before "
     "12:00, Owen Blackwood and Felix Brandt did not show up: mark theirs no_show and add the no_show_warning "
     "flag to each of those two patients. Mark his other booked appointments that started before 12:00 as "
     "completed. Appointments starting at 12:00 or later, cancelled ones and other clinicians' appointments "
     "are left alone.",
     [["get_clinic_info", {}], ["list_appointments", {"clinician_id": "C3", "date": "2026-05-18"}],
      ["set_appointment_status", {"appointment_id": "A501", "status": "completed"}],
      ["set_appointment_status", {"appointment_id": "A502", "status": "no_show"}],
      ["set_appointment_status", {"appointment_id": "A503", "status": "completed"}],
      ["set_appointment_status", {"appointment_id": "A504", "status": "no_show"}],
      ["update_patient", {"patient_id": "P10", "fields": {"add_flags": ["no_show_warning"]}}],
      ["update_patient", {"patient_id": "P12", "fields": {"add_flags": ["no_show_warning"]}}]],
     [["set_appointment_status", {"appointment_id": "A501", "status": "completed"}],
      ["set_appointment_status", {"appointment_id": "A502", "status": "no_show"}],
      ["set_appointment_status", {"appointment_id": "A503", "status": "completed"}],
      ["set_appointment_status", {"appointment_id": "A504", "status": "no_show"}],
      ["set_appointment_status", {"appointment_id": "A509", "status": "completed"}],
      ["update_patient", {"patient_id": "P10", "fields": {"add_flags": ["no_show_warning"]}}],
      ["update_patient", {"patient_id": "P12", "fields": {"add_flags": ["no_show_warning"]}}]],
     lambda s, i: _final(s, i, changes={
         "appointments": {"A501": {"status": "completed"}, "A502": {"status": "no_show"},
                          "A503": {"status": "completed"}, "A504": {"status": "no_show"}},
         "patients": {"P10": {"flags": ["no_show_warning"]}, "P12": {"flags": ["no_show_warning", "vip"]}}}))

_add("T36", "clinic", "medium", _clinic([
    ("P03", "C3", "2026-05-20", "10:00", "checkup"),
    ("P03", "C3", "2026-05-27", "10:00", "checkup"),
    ("P03", "C3", "2026-06-03", "10:00", "follow_up"),
    ("P03", "C5", "2026-05-22", "14:00", "checkup"),
    ("P03", "C4", "2026-05-19", "09:00", "vaccination", "cancelled"),
    ("P03", "C4", "2026-05-21", "09:00", "vaccination"),
    ("P03", "C4", "2026-05-28", "09:00", "vaccination"),
    ("P08", "C3", "2026-05-27", "10:30", "checkup")]),
     "Tobias Reinholt thinks he has been double-booked. Look only at his appointments that are currently "
     "booked: wherever two or more of them have the same appointment type with the same clinician, keep the "
     "earliest one and cancel the later ones with reason duplicate. Appointments that are already cancelled "
     "don't count as bookings and stay as they are. Everything else of his stays booked.",
     [["find_patients", {"query": "Reinholt"}], ["list_appointments", {"patient_id": "P03"}],
      ["cancel_appointment", {"appointment_id": "A502", "reason": "duplicate"}],
      ["cancel_appointment", {"appointment_id": "A507", "reason": "duplicate"}]],
     [["cancel_appointment", {"appointment_id": "A502", "reason": "duplicate"}],
      ["cancel_appointment", {"appointment_id": "A504", "reason": "duplicate"}],
      ["cancel_appointment", {"appointment_id": "A507", "reason": "duplicate"}]],
     lambda s, i: _final(s, i, changes={"appointments": {
         "A502": {"status": "cancelled", "cancel_reason": "duplicate"},
         "A507": {"status": "cancelled", "cancel_reason": "duplicate"}}}))

_add("T37", "clinic", "hard", _clinic([
    ("P09", "C4", "2026-06-18", "10:00", "follow_up"),
    ("P10", "C4", "2026-06-18", "10:15", "vaccination"),
    ("P11", "C4", "2026-05-21", "09:45", "vaccination"),
    ("P07", "C4", "2026-06-18", "10:45", "vaccination")]),
     "Arjun Mehta needs two vaccination doses with Nurse Reyes. Book the first for 2026-05-21 at 10:00. Book "
     "the second exactly 28 days after the first, also at 10:00; but if Nurse Reyes already has something "
     "overlapping at that time, use the earliest later start time that same day at which the appointment fits. "
     "Don't move or cancel anyone else's appointments.",
     [["get_clinic_info", {}], ["find_patients", {"query": "Arjun"}],
      ["book_appointment", {"patient_id": "P06", "clinician_id": "C4", "date": "2026-05-21", "time": "10:00",
                            "type": "vaccination"}],
      ["book_appointment", {"patient_id": "P06", "clinician_id": "C4", "date": "2026-06-18", "time": "10:00",
                            "type": "vaccination"}],
      ["list_appointments", {"clinician_id": "C4", "date": "2026-06-18"}],
      ["book_appointment", {"patient_id": "P06", "clinician_id": "C4", "date": "2026-06-18", "time": "10:30",
                            "type": "vaccination"}]],
     [["book_appointment", {"patient_id": "P06", "clinician_id": "C4", "date": "2026-05-21", "time": "10:00",
                            "type": "vaccination"}],
      ["book_appointment", {"patient_id": "P06", "clinician_id": "C4", "date": "2026-06-18", "time": "11:00",
                            "type": "vaccination"}]],
     lambda s, i: _final(s, i, new={"appointments": [
         {"patient": "P06", "clinician": "C4", "date": "2026-05-21", "time": "10:00", "type": "vaccination",
          "status": "booked"},
         {"patient": "P06", "clinician": "C4", "date": "2026-06-18", "time": "10:30", "type": "vaccination",
          "status": "booked"}]}),
     ref_errors=[3])

_add("T38", "clinic", "medium", _clinic([
    ("P04", "C1", "2026-05-27", "11:00", "consult"),
    ("P05", "C3", "2026-05-27", "11:00", "consult"),
    ("P08", "C1", "2026-05-28", "11:00", "checkup")]),
     "Helen Marsh (Marsh with an s, not Helen March) rang. Her phone number is now 555-0142, please update it. "
     "She also asked whether her consult next week could move to exactly one day earlier, same time, same "
     "doctor. Only do that if her doctor works that day and is free at that time; if not, leave the appointment "
     "exactly as it is. Don't switch her to another doctor or another time.",
     [["find_patients", {"query": "Helen"}], ["list_appointments", {"patient_id": "P04"}],
      ["get_clinic_info", {}],
      ["update_patient", {"patient_id": "P04", "fields": {"phone": "555-0142"}}]],
     [["update_patient", {"patient_id": "P04", "fields": {"phone": "555-0142"}}],
      ["reschedule_appointment", {"appointment_id": "A501", "new": {"date": "2026-05-26", "clinician_id": "C3"}}]],
     lambda s, i: _final(s, i, changes={"patients": {"P04": {"phone": "555-0142"}}}))

_WL39 = [("P06", "C1", "follow_up"), ("P10", "C1", "checkup"), ("P07", "C3", "checkup"),
         ("P11", "C1", "checkup"), ("P12", "C1", "checkup")]

_add("T39", "clinic", "very hard", _clinic([
    ("P08", "C1", "2026-05-20", "14:00", "checkup"),
    ("P10", "C3", "2026-05-20", "14:15", "follow_up"),
    ("P12", "C1", "2026-05-21", "09:00", "consult"),
    ("P08", "C3", "2026-05-27", "14:00", "checkup")], waitlist=_WL39),
     "Samuel Petrov has asked to cancel his checkup with Dr. Lindqvist this Wednesday; cancel it with reason "
     "patient_request. Then offer the freed slot to Dr. Lindqvist's waitlist in list order: the first person "
     "waiting for a checkup with her who has no other booked appointment overlapping that time gets booked "
     "into exactly that date and time, and is removed from the waitlist. Everyone else stays on the waitlist.",
     [["find_patients", {"query": "Petrov"}], ["list_appointments", {"patient_id": "P08"}],
      ["cancel_appointment", {"appointment_id": "A501", "reason": "patient_request"}],
      ["list_waitlist", {"clinician_id": "C1"}],
      ["book_appointment", {"patient_id": "P10", "clinician_id": "C1", "date": "2026-05-20", "time": "14:00",
                            "type": "checkup"}],
      ["book_appointment", {"patient_id": "P11", "clinician_id": "C1", "date": "2026-05-20", "time": "14:00",
                            "type": "checkup"}],
      ["manage_waitlist", {"action": "remove", "patient_id": "P11", "clinician_id": "C1", "type": "checkup"}]],
     [["cancel_appointment", {"appointment_id": "A501", "reason": "patient_request"}],
      ["book_appointment", {"patient_id": "P12", "clinician_id": "C1", "date": "2026-05-20", "time": "14:00",
                            "type": "checkup"}],
      ["manage_waitlist", {"action": "remove", "patient_id": "P12", "clinician_id": "C1", "type": "checkup"}]],
     lambda s, i: _final(s, i, changes={
         "appointments": {"A501": {"status": "cancelled", "cancel_reason": "patient_request"}},
         "waitlist": [w for w in i["waitlist"] if w["patient"] != "P11"]},
         new={"appointments": [{"patient": "P11", "clinician": "C1", "date": "2026-05-20", "time": "14:00",
                                "type": "checkup", "status": "booked"}]}),
     ref_errors=[4])

_add("T40", "clinic", "hard", _clinic([
    ("P06", "C3", "2026-05-04", "09:00", "checkup", "no_show"),
    ("P06", "C2", "2026-05-07", "09:00", "follow_up", "no_show"),
    ("P06", "C3", "2026-05-12", "09:00", "checkup", "no_show"),
    ("P07", "C3", "2026-04-27", "10:00", "checkup", "no_show"),
    ("P07", "C3", "2026-05-04", "10:00", "checkup", "no_show"),
    ("P07", "C3", "2026-05-11", "10:00", "checkup", "completed"),
    ("P08", "C2", "2026-05-06", "11:00", "consult", "no_show"),
    ("P08", "C4", "2026-05-14", "11:00", "vaccination", "no_show"),
    ("P08", "C3", "2026-05-15", "11:00", "checkup", "cancelled"),
    ("P09", "C3", "2026-05-11", "13:00", "follow_up", "no_show"),
    ("P10", "C2", "2026-04-20", "13:00", "checkup", "no_show"),
    ("P11", "C3", "2026-05-05", "15:00", "checkup", "completed")],
    flags={"P06": ["deposit_required"], "P09": ["deposit_required", "interpreter"],
           "P10": ["deposit_required"], "P11": ["vip"]}),
     "Deposit policy clean-up. Count, per patient, the appointments dated in May 2026 whose status is no_show "
     "(any clinician). Every patient with two or more of those must have the deposit_required flag, and no "
     "other patient may have it. Add or remove that flag where needed so this is true. Don't change any other "
     "flag, and don't change any appointments.",
     [["list_appointments", {"status": "no_show"}], ["find_patients", {"query": ""}],
      ["update_patient", {"patient_id": "P08", "fields": {"add_flags": ["deposit_required"]}}],
      ["update_patient", {"patient_id": "P09", "fields": {"remove_flags": ["deposit_required"]}}],
      ["update_patient", {"patient_id": "P10", "fields": {"remove_flags": ["deposit_required"]}}]],
     [["update_patient", {"patient_id": "P08", "fields": {"add_flags": ["deposit_required"]}}],
      ["update_patient", {"patient_id": "P07", "fields": {"add_flags": ["deposit_required"]}}],
      ["update_patient", {"patient_id": "P09", "fields": {"remove_flags": ["deposit_required"]}}],
      ["update_patient", {"patient_id": "P10", "fields": {"remove_flags": ["deposit_required"]}}]],
     lambda s, i: _final(s, i, changes={"patients": {
         "P08": {"flags": ["deposit_required"]}, "P09": {"flags": ["interpreter"]}, "P10": {"flags": []}}}))


# --------------------------------------------------------------------------
# pilot tasks (throwaway)
# --------------------------------------------------------------------------
_add("TP1", "inventory", "pilot", _inv(),
     "Please move 10 of the M8 wing nuts from MAIN to ANNEX, and once that's done flag the wing nut item as "
     "reviewed. Look the SKU up in the system rather than guessing it. Don't touch any other item, and don't "
     "create or change any purchase orders.",
     [["list_items", {"query": "wing nut"}],
      ["transfer_stock", {"sku": "WN-08", "from_location": "MAIN", "to_location": "ANNEX", "qty": 10}],
      ["set_item_flag", {"sku": "WN-08", "flag": "reviewed", "value": True}]],
     [["transfer_stock", {"sku": "WN-08", "from_location": "MAIN", "to_location": "ANNEX", "qty": 10}]],
     lambda s, i: _final(s, i, changes={"items": {"WN-08": {
         "stock": {"MAIN": 70, "ANNEX": 10, "QUAR": 0},
         "flags": {"reviewed": True, "hold": False, "discontinued": False}}}}))

_add("TP2", "calendar", "pilot", _cal(_CAL16),
     "For Friday this week: cancel the 'Planning pre-read' meeting, it isn't needed any more, and add Hiro "
     "Tanabe as an attendee to 'Quarterly planning' that afternoon. Keep that meeting's time, room and other "
     "attendees as they are, and don't change anything else on the calendar.",
     [["get_calendar_info", {}], ["list_events", {"date": _FRI}], ["find_people", {"query": "Hiro"}],
      ["cancel_event", {"event_id": "E102"}], ["set_attendees", {"event_id": "E101", "add": ["U09"]}]],
     [["cancel_event", {"event_id": "E101"}], ["set_attendees", {"event_id": "E102", "add": ["U09"]}]],
     lambda s, i: _final(s, i, changes={"events": {
         "E102": None, "E101": {"attendees": ["U01", "U02", "U08", "U09", "U10"]}}}))

_add("TP3", "tickets", "pilot", _trk(copy.deepcopy(_TRK18), on_leave=["USR-3"]),
     "The ticket 'Rotate signing keys' has become critical. Set its priority to urgent, assign it to Rafael "
     "Ortiz, and add the infra label while keeping its existing labels. There is no need to change its status, "
     "and no other ticket should be modified in any way.",
     [["search_tickets", {"query": "Rotate signing keys"}], ["list_users", {}],
      ["update_ticket", {"ticket_id": "TK-208", "fields": {"priority": "urgent", "assignee_id": "USR-1"}}],
      ["edit_labels", {"ticket_id": "TK-208", "add": ["infra"]}]],
     [["update_ticket", {"ticket_id": "TK-208", "fields": {"priority": "urgent", "assignee_id": "USR-1"}}]],
     lambda s, i: _final(s, i, changes={"tickets": {"TK-208": {
         "priority": "urgent", "assignee": "USR-1", "labels": ["infra", "security"]}}}))


# --------------------------------------------------------------------------
# self-verification
# --------------------------------------------------------------------------
def _is_err(res):
    return isinstance(res, dict) and "error" in res


def _strings(obj, acc):
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.add(k)
            _strings(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _strings(v, acc)
    elif isinstance(obj, str):
        acc.add(obj)


_GARBAGE = [None, "", "zzz", "/", "/a//b", -1, 0, 3, 10 ** 12, 1.5, 2.0, float("inf"), float("nan"), True, False,
            [], [None], [{}], ["a", 1], [[1]], {}, {"x": {"y": [1]}}, {"sku": 1, "qty": "2"},
            "2026-13-45", "25:99", "2026-04-15", "2026-05-20", "09:00", "9:00", "é中"]


def _safe_call(env, name, args, label):
    before = copy.deepcopy(env.state)
    try:
        res = env.call(name, args)
    except Exception as e:  # pragma: no cover - this is what the fuzz is for
        raise AssertionError("%s: call raised %r for %r %r" % (label, e, name, args))
    json.dumps(res)
    if _is_err(res):
        assert env.state == before, "%s: state changed on error for %r %r" % (label, name, args)
    json.dumps(env.state)
    return res


def _fuzz():
    rng = random.Random(20261005)
    calls = 0
    for ename in sorted(ENVS):
        cls = ENVS[ename]
        inits = [t["init"] for t in TASKS if t["env"] == ename]
        pool = set()
        _strings(inits[0], pool)
        pool = sorted(pool)
        names = [t["function"]["name"] for t in cls.TOOLS]
        env = cls(inits[0])
        for name in names + [None, 5, "nope", "", [], {}, 1.5, "get_item; drop"]:
            for args in _GARBAGE + ["{}", 7]:
                _safe_call(env, name, args, ename)
                calls += 1

        def rand_value(schema, depth=0):
            r = rng.random()
            if r < 0.3 or depth > 3:
                return rng.choice(_GARBAGE)
            t = schema.get("type")
            t = [x for x in (t if isinstance(t, list) else [t]) if x != "null"][0]
            if t == "string":
                if "enum" in schema and rng.random() < 0.8:
                    return rng.choice(schema["enum"])
                return rng.choice(pool)
            if t == "integer":
                return rng.choice([-5, 0, 1, 2, 6, 12, 25, 50, 100, 1000])
            if t == "boolean":
                return rng.random() < 0.5
            if t == "array":
                return [rand_value(schema["items"], depth + 1) for _ in range(rng.randint(0, 3))]
            if t == "object":
                out = {}
                for k, sub in schema.get("properties", {}).items():
                    if k in schema.get("required", []) or rng.random() < 0.6:
                        out[k] = rand_value(sub, depth + 1)
                if rng.random() < 0.05:
                    out["bogus"] = 1
                return out
            return None

        for n in range(2500):
            if n % 250 == 0:
                env = cls(rng.choice(inits))
            tool = rng.choice(cls.TOOLS)["function"]
            _safe_call(env, tool["name"], rand_value(tool["parameters"]), ename)
            calls += 1
    # mutate every argument of every reference call with every garbage value
    for t in TASKS:
        for step, (name, args) in enumerate(t["reference"]):
            for key in list(args) + ["__extra__"]:
                for g in _GARBAGE:
                    env = ENVS[t["env"]](t["init"])
                    for pname, pargs in t["reference"][:step]:
                        env.call(pname, copy.deepcopy(pargs))
                    bad = copy.deepcopy(args)
                    bad[key] = g
                    _safe_call(env, name, bad, t["id"])
                    calls += 1
            for key in args:
                env = ENVS[t["env"]](t["init"])
                bad = copy.deepcopy(args)
                del bad[key]
                _safe_call(env, name, bad, t["id"])
                calls += 1
    return calls


def _verify():
    ids = [t["id"] for t in TASKS]
    assert ids == ["T%02d" % n for n in range(1, 41)] + ["TP1", "TP2", "TP3"], ids
    assert len(ENVS) == 5
    for ename, cls in ENVS.items():
        assert 6 <= len(cls.TOOLS) <= 10, (ename, len(cls.TOOLS))
        json.dumps(cls.TOOLS)
        for tool in cls.TOOLS:
            fn = tool["function"]
            assert tool["type"] == "function" and fn["parameters"]["type"] == "object"
            assert hasattr(cls, "_t_" + fn["name"]), fn["name"]
            for r in fn["parameters"]["required"]:
                assert r in fn["parameters"]["properties"], (fn["name"], r)
        n = len([t for t in TASKS[:40] if t["env"] == ename])
        assert n == 8, (ename, n)
    diffs = [t["difficulty"] for t in TASKS[:40]]
    assert (diffs.count("medium"), diffs.count("hard"), diffs.count("very hard")) == (10, 22, 8), \
        (diffs.count("medium"), diffs.count("hard"), diffs.count("very hard"))
    ok = 0
    for t in TASKS:
        tid = t["id"]
        words = len(t["prompt"].split())
        assert 40 <= words <= 140, (tid, "prompt words", words)
        assert 3 <= len(t["reference"]) <= 8, (tid, "reference length", len(t["reference"]))
        json.dumps(t["init"])
        json.dumps(t["reference"])
        json.dumps(t["trap"])
        # (a) untouched initial state must fail
        env = ENVS[t["env"]](t["init"])
        assert env.state == t["init"] and env.state is not t["init"]
        assert t["check"](env.state) is False, (tid, "check passes on the initial state")
        # (b) reference solves it; errors only where intended
        for n, (name, args) in enumerate(t["reference"]):
            res = env.call(name, copy.deepcopy(args))
            json.dumps(res)
            assert _is_err(res) == (n in t["ref_errors"]), (tid, "reference step", n, name, res)
        assert t["check"](env.state) is True, (tid, "reference does not satisfy check")
        json.dumps(env.state)
        # read-only tools after the solution must not disturb the result
        for tool in ENVS[t["env"]].TOOLS:
            fn = tool["function"]
            if not fn["parameters"]["required"]:
                assert not _is_err(env.call(fn["name"], {})) or fn["name"] == "list_appointments", (tid, fn["name"])
        assert t["check"](env.state) is True, (tid, "read tools changed the state")
        # (d) trap must fail
        env = ENVS[t["env"]](t["init"])
        for name, args in t["trap"]:
            json.dumps(env.call(name, copy.deepcopy(args)))
        assert env.state != t["init"], (tid, "trap changed nothing")
        assert t["check"](env.state) is False, (tid, "trap passes the check")
        # init must not have been mutated by any of the above
        assert t["check"](copy.deepcopy(t["init"])) is False
        ok += 1
    calls = _fuzz()
    for t in TASKS:   # fuzz must not have leaked into the fixtures
        env = ENVS[t["env"]](t["init"])
        for name, args in t["reference"]:
            env.call(name, copy.deepcopy(args))
        assert t["check"](env.state) is True, (t["id"], "fixture mutated by fuzz")
    return ok, calls


if __name__ == "__main__":
    _ok, _calls = _verify()
    print("fuzz: %d calls, 0 exceptions, state unchanged on every error" % _calls)
    print("OK %d/%d" % (_ok, len(TASKS)))
