# -*- coding: utf-8 -*-
"""Mock tool environments + long multi-step tool-calling tasks (bonsai2 ROUND 2 test set).

Stdlib only; runs on Python 3.9 and 3.12.  Tasks are graded on the FINAL STATE
of the mock environment (task["check"](env.state)).

Layout
  ENVS   name -> environment class (TOOLS in OpenAI chat-completions format,
         __init__(init), call(name, args) which never raises and leaves the
         state unchanged whenever it returns {"error": ...})
  TASKS  T01..T30 (test set, 6 per environment) then TP1..TP6 (calibration,
         same style and difficulty; one per environment plus one extra)

Differences from round 1 (items/tool_items.py)
  * five new domains: bank ledger, deploy pipeline, course registration,
    fleet dispatch, hotel bookings
  * references need 9-16 calls; rules live in policy read-tools; larger states
  * no schema uses a union type and no task needs null / "" as an argument
  * every entity a prompt names is mechanically checked to exist in init

Run this file directly to self-verify:  prints "OK 36/36".
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
    if v is None:
        return None, "'%s' must not be null" % path
    if t == "string":
        if not isinstance(v, str):
            return None, "'%s' must be a string" % path
        if "enum" in schema and v not in schema["enum"]:
            return None, "'%s' must be one of: %s" % (path, ", ".join(schema["enum"]))
        return v, None
    if t == "integer":
        if isinstance(v, bool):
            return None, "'%s' must be an integer" % path
        if isinstance(v, str) and re.match(r"^-?\d{1,9}$", v.strip()):
            v = int(v.strip())   # "250" for 250 is a tool-call formatting slip, not a reasoning error
        if isinstance(v, float):
            if v != v or v in (float("inf"), float("-inf")) or v != int(v):
                return None, "'%s' must be an integer" % path
            v = int(v)
        if not isinstance(v, int):
            return None, "'%s' must be an integer" % path
        if abs(v) > 10 ** 9:
            return None, "'%s' is out of range" % path
        if "minimum" in schema and v < schema["minimum"]:
            return None, "'%s' must be >= %d" % (path, schema["minimum"])
        if "maximum" in schema and v > schema["maximum"]:
            return None, "'%s' must be <= %d" % (path, schema["maximum"])
        return v, None
    if t == "boolean":
        if isinstance(v, str) and v.strip().lower() in ("true", "false"):
            v = v.strip().lower() == "true"   # same leniency for "true"/"false" sent as strings
        if not isinstance(v, bool):
            return None, "'%s' must be true or false" % path
        return v, None
    if t == "array":
        if not isinstance(v, list):
            return None, "'%s' must be an array" % path
        out = []
        for n, item in enumerate(v):
            val, err = _norm(schema["items"], item, "%s[%d]" % (path, n))
            if err:
                return None, err
            out.append(val)
        return out, None
    if t == "object":
        if not isinstance(v, dict):
            return None, "'%s' must be an object" % path
        props = schema.get("properties", {})
        required = schema.get("required", [])
        pre = "" if path == "arguments" else path + "."
        out = {}
        for k in v:
            if not isinstance(k, str) or k not in props:
                return None, "unexpected argument '%s%s' (allowed: %s)" % (
                    pre, str(k)[:40], ", ".join(sorted(props)) or "none")
        for k in required:
            if k not in v:
                return None, "missing required argument '%s%s'" % (pre, k)
        for k, val in v.items():
            if val is None and k not in required:
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


def _i(desc, minimum=None, maximum=None):
    d = {"type": "integer", "description": desc}
    if minimum is not None:
        d["minimum"] = minimum
    if maximum is not None:
        d["maximum"] = maximum
    return d


def _b(desc):
    return {"type": "boolean", "description": desc}


_PAGE = _i("Page number, starting at 1 (default 1).", 1)


def _pdate(s, what="date"):
    if not isinstance(s, str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        raise _Rule("%s must be formatted YYYY-MM-DD, got '%s'" % (what, str(s)[:30]))
    try:
        return datetime.date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    except ValueError:
        raise _Rule("%s '%s' is not a real calendar date" % (what, s))


def _ptime(s, what="time"):
    if not isinstance(s, str) or not re.match(r"^\d{2}:\d{2}$", s):
        raise _Rule("%s must be formatted HH:MM (24h), got '%s'" % (what, str(s)[:30]))
    h, m = int(s[0:2]), int(s[3:5])
    if h > 23 or m > 59:
        raise _Rule("%s '%s' is not a valid time" % (what, s))
    return h * 60 + m


def _paged(rows, page, size):
    """Returns (meta, slice). Raises _Rule for a page that does not exist."""
    pages = max(1, (len(rows) + size - 1) // size)
    if page > pages:
        raise _Rule("page %d does not exist (there are %d page(s))" % (page, pages))
    return ({"page": page, "pages": pages, "total_results": len(rows)},
            rows[(page - 1) * size: page * size])


_DAYNAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_READ_PREFIXES = ("get_", "list_", "find_", "search_")


def _is_read(name):
    return isinstance(name, str) and name.startswith(_READ_PREFIXES)


def _clone(state):
    """Deep copy of a JSON-shaped state (much faster than copy.deepcopy)."""
    return json.loads(json.dumps(state))


class _Env(object):
    TOOLS = []

    def __init__(self, init):
        self.state = _clone(init)

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
        snap = _clone(self.state)
        try:
            res = getattr(self, "_t_" + name)(args)
            res = json.loads(json.dumps(res))
            json.dumps(self.state)
        except _Rule as e:
            self._restore(snap)
            return {"error": str(e)}
        except Exception as e:
            self._restore(snap)
            return {"error": "internal error (%s); nothing was changed" % type(e).__name__}
        if isinstance(res, dict) and "error" in res:
            self._restore(snap)
        return res


# --------------------------------------------------------------------------
# 1. bank: customers, sub-accounts, holds, transactions, scheduled payments
# --------------------------------------------------------------------------
_HOLD_REASONS = ["pending_card", "deposit_check", "earmark", "dispute", "legal"]


class BankEnv(_Env):
    TOOLS = [
        _fn("get_bank_info", "Today's date and the bank's operating policy (limits and rules that the write tools enforce)."),
        _fn("find_customers", "Search customers by name (case-insensitive substring). Returns customer ids.",
            {"query": _s("Text that must appear in the customer name.")}, ["query"]),
        _fn("list_accounts", "All accounts of one customer: id, type, nickname, balance, status. Holds are not shown here.",
            {"customer_id": _s("Customer id, e.g. C-101.")}, ["customer_id"]),
        _fn("get_account", "One account in detail: balance, total of active holds, available funds, "
            "number of active holds and of pending scheduled payments.",
            {"account_id": _s("Account id, e.g. A-2001.")}, ["account_id"]),
        _fn("list_transactions", "Posted transactions of one account, newest first, 8 per page. "
            "Amounts are signed (negative = money out).",
            {"account_id": _s("Account id."),
             "type": _s("Only transactions of this type.", ["card", "deposit", "fee", "transfer_in", "transfer_out"]),
             "page": _PAGE}, ["account_id"]),
        _fn("list_holds", "Holds on one account (all statuses unless filtered).",
            {"account_id": _s("Account id."),
             "status": _s("Only holds in this status.", ["active", "released"])}, ["account_id"]),
        _fn("list_scheduled", "Scheduled outgoing payments of one account, by date, 6 per page.",
            {"account_id": _s("Account id."),
             "status": _s("Only payments in this status.", ["pending", "executed", "cancelled"]),
             "page": _PAGE}, ["account_id"]),
        _fn("transfer", "Move money between two open accounts immediately.",
            {"from_account": _s("Account id to debit."), "to_account": _s("Account id to credit."),
             "amount": _i("Whole currency units.", 1)}, ["from_account", "to_account", "amount"]),
        _fn("place_hold", "Place a new active hold on an account (reduces its available funds).",
            {"account_id": _s("Account id."), "amount": _i("Amount to hold.", 1),
             "reason": _s("Hold reason.", _HOLD_REASONS),
             "expires": _s("Expiry date, YYYY-MM-DD (must be after today).")},
            ["account_id", "amount", "reason", "expires"]),
        _fn("release_hold", "Release an active hold.", {"hold_id": _s("Hold id, e.g. H-301.")}, ["hold_id"]),
        _fn("reverse_transaction", "Reverse a fee or card transaction: the amount is credited back to the account "
            "and the transaction is marked reversed.",
            {"transaction_id": _s("Transaction id, e.g. X-5101.")}, ["transaction_id"]),
        _fn("schedule_payment", "Schedule a new outgoing payment from an account to a registered payee.",
            {"from_account": _s("Account id to debit."), "payee_id": _s("Payee id, e.g. P-01."),
             "amount": _i("Amount.", 1), "date": _s("Execution date, YYYY-MM-DD.")},
            ["from_account", "payee_id", "amount", "date"]),
        _fn("cancel_scheduled", "Cancel a pending scheduled payment.",
            {"scheduled_id": _s("Scheduled payment id, e.g. S-401.")}, ["scheduled_id"]),
        _fn("close_account", "Close an account.", {"account_id": _s("Account id.")}, ["account_id"]),
    ]

    def _acct(self, aid, must_open=False):
        a = self.state["accounts"].get(aid)
        if a is None:
            raise _Rule("unknown account '%s'" % aid[:30])
        if must_open and a["status"] != "open":
            raise _Rule("account %s is closed" % aid)
        return a

    def _held(self, aid):
        return sum(h["amount"] for h in self.state["holds"].values()
                   if h["account"] == aid and h["status"] == "active")

    def _avail(self, aid):
        return self.state["accounts"][aid]["balance"] - self._held(aid)

    def _today(self):
        return _pdate(self.state["today"])

    def _t_get_bank_info(self, a):
        p = self.state["policy"]
        return {"today": self.state["today"], "policy": {
            "max_single_transfer": p["max_single_transfer"],
            "fee_reversal_window_days": p["fee_reversal_days"],
            "card_reversal_window_days": p["card_reversal_days"],
            "scheduled_payment_max_days_ahead": p["schedule_max_days"],
            "rules": [
                "Available funds = balance minus the total of ACTIVE holds. Transfers and new holds can only use available funds.",
                "A single transfer may not exceed max_single_transfer; larger amounts must be split into several transfers.",
                "Holds: staff may release 'earmark' holds at any time, and 'pending_card' or 'deposit_check' holds only "
                "after their expiry date has passed. 'dispute' and 'legal' holds can only be released by the disputes "
                "team, not through this system.",
                "Reversals: a fee can be reversed up to fee_reversal_window_days after it was charged, a card payment "
                "up to card_reversal_window_days. Each transaction can be reversed only once.",
                "An account can be closed only when its balance is 0 and it has no active holds and no pending scheduled payments.",
                "Scheduled payments must be dated after today and at most scheduled_payment_max_days_ahead days ahead.",
            ]}}

    def _t_find_customers(self, a):
        q = a["query"].strip().lower()
        out = [{"customer_id": k, "name": v["name"], "segment": v["segment"]}
               for k, v in sorted(self.state["customers"].items()) if q in v["name"].lower()]
        return {"customers": out}

    def _t_list_accounts(self, a):
        if a["customer_id"] not in self.state["customers"]:
            raise _Rule("unknown customer '%s'" % a["customer_id"][:30])
        out = [{"account_id": k, "type": v["type"], "nickname": v["nickname"], "balance": v["balance"],
                "status": v["status"]}
               for k, v in sorted(self.state["accounts"].items()) if v["owner"] == a["customer_id"]]
        return {"customer_id": a["customer_id"], "accounts": out}

    def _t_get_account(self, a):
        aid = a["account_id"]
        ac = self._acct(aid)
        return {"account_id": aid, "owner": ac["owner"], "owner_name": self.state["customers"][ac["owner"]]["name"],
                "type": ac["type"], "nickname": ac["nickname"], "status": ac["status"],
                "balance": ac["balance"], "active_holds_total": self._held(aid), "available": self._avail(aid),
                "active_holds": len([1 for h in self.state["holds"].values()
                                     if h["account"] == aid and h["status"] == "active"]),
                "pending_scheduled_payments": len([1 for s in self.state["scheduled"].values()
                                                   if s["from"] == aid and s["status"] == "pending"])}

    def _t_list_transactions(self, a):
        self._acct(a["account_id"])
        rows = [(v["date"], k, v) for k, v in self.state["transactions"].items()
                if v["account"] == a["account_id"] and ("type" not in a or v["type"] == a["type"])]
        rows.sort(reverse=True)
        meta, rows = _paged(rows, a.get("page", 1), 8)
        meta["account_id"] = a["account_id"]
        meta["transactions"] = [{"transaction_id": k, "date": d, "type": v["type"], "amount": v["amount"],
                                 "description": v["description"], "reversed": v["reversed"]} for d, k, v in rows]
        return meta

    def _t_list_holds(self, a):
        self._acct(a["account_id"])
        out = [{"hold_id": k, "amount": v["amount"], "reason": v["reason"], "placed": v["placed"],
                "expires": v["expires"], "status": v["status"]}
               for k, v in sorted(self.state["holds"].items())
               if v["account"] == a["account_id"] and ("status" not in a or v["status"] == a["status"])]
        return {"account_id": a["account_id"], "holds": out}

    def _t_list_scheduled(self, a):
        self._acct(a["account_id"])
        rows = [(v["date"], k, v) for k, v in self.state["scheduled"].items()
                if v["from"] == a["account_id"] and ("status" not in a or v["status"] == a["status"])]
        rows.sort()
        meta, rows = _paged(rows, a.get("page", 1), 6)
        meta["account_id"] = a["account_id"]
        meta["scheduled_payments"] = [
            {"scheduled_id": k, "date": d, "payee_id": v["payee"], "payee_name": self.state["payees"][v["payee"]],
             "amount": v["amount"], "status": v["status"]} for d, k, v in rows]
        return meta

    def _t_transfer(self, a):
        src = self._acct(a["from_account"], True)
        dst = self._acct(a["to_account"], True)
        amt = a["amount"]
        if a["from_account"] == a["to_account"]:
            raise _Rule("from_account and to_account are the same account")
        lim = self.state["policy"]["max_single_transfer"]
        if amt > lim:
            raise _Rule("amount %d exceeds the single-transfer limit of %d; split it into several transfers" % (amt, lim))
        av = self._avail(a["from_account"])
        if amt > av:
            raise _Rule("insufficient available funds in %s: balance %d, active holds %d, available %d" % (
                a["from_account"], src["balance"], self._held(a["from_account"]), av))
        src["balance"] -= amt
        dst["balance"] += amt
        self.state["log"].append({"op": "transfer", "from": a["from_account"], "to": a["to_account"], "amount": amt})
        return {"ok": True, "from_account": a["from_account"], "from_balance": src["balance"],
                "to_account": a["to_account"], "to_balance": dst["balance"]}

    def _t_place_hold(self, a):
        self._acct(a["account_id"], True)
        exp = _pdate(a["expires"], "expires")
        if exp <= self._today():
            raise _Rule("expires must be after today (%s)" % self.state["today"])
        av = self._avail(a["account_id"])
        if a["amount"] > av:
            raise _Rule("cannot hold %d: only %d available in %s" % (a["amount"], av, a["account_id"]))
        hid = "H-%d" % self.state["next_hold"]
        self.state["next_hold"] += 1
        self.state["holds"][hid] = {"account": a["account_id"], "amount": a["amount"], "reason": a["reason"],
                                    "placed": self.state["today"], "expires": a["expires"], "status": "active"}
        return {"ok": True, "hold_id": hid, "available_now": self._avail(a["account_id"])}

    def _t_release_hold(self, a):
        h = self.state["holds"].get(a["hold_id"])
        if h is None:
            raise _Rule("unknown hold '%s'" % a["hold_id"][:30])
        if h["status"] != "active":
            raise _Rule("hold %s is not active (status: %s)" % (a["hold_id"], h["status"]))
        if h["reason"] in ("dispute", "legal"):
            raise _Rule("hold %s has reason '%s' and can only be released by the disputes team" % (a["hold_id"], h["reason"]))
        if h["reason"] in ("pending_card", "deposit_check") and _pdate(h["expires"]) >= self._today():
            raise _Rule("hold %s (%s) has not passed its expiry date %s yet and cannot be released" % (
                a["hold_id"], h["reason"], h["expires"]))
        h["status"] = "released"
        return {"ok": True, "hold_id": a["hold_id"], "account_id": h["account"], "available_now": self._avail(h["account"])}

    def _t_reverse_transaction(self, a):
        x = self.state["transactions"].get(a["transaction_id"])
        if x is None:
            raise _Rule("unknown transaction '%s'" % a["transaction_id"][:30])
        if x["type"] not in ("fee", "card"):
            raise _Rule("only fee and card transactions can be reversed; %s is of type %s" % (a["transaction_id"], x["type"]))
        if x["reversed"]:
            raise _Rule("transaction %s has already been reversed" % a["transaction_id"])
        age = (self._today() - _pdate(x["date"])).days
        lim = self.state["policy"]["fee_reversal_days" if x["type"] == "fee" else "card_reversal_days"]
        if age > lim:
            raise _Rule("transaction %s is %d days old; %s transactions can only be reversed within %d days" % (
                a["transaction_id"], age, x["type"], lim))
        ac = self._acct(x["account"], True)
        x["reversed"] = True
        ac["balance"] -= x["amount"]
        return {"ok": True, "transaction_id": a["transaction_id"], "credited": -x["amount"],
                "account_id": x["account"], "balance": ac["balance"]}

    def _t_schedule_payment(self, a):
        self._acct(a["from_account"], True)
        if a["payee_id"] not in self.state["payees"]:
            raise _Rule("unknown payee '%s'" % a["payee_id"][:30])
        d = _pdate(a["date"])
        ahead = (d - self._today()).days
        if ahead <= 0:
            raise _Rule("date must be after today (%s)" % self.state["today"])
        if ahead > self.state["policy"]["schedule_max_days"]:
            raise _Rule("date is more than %d days ahead" % self.state["policy"]["schedule_max_days"])
        if a["amount"] > self.state["policy"]["max_single_transfer"]:
            raise _Rule("amount exceeds the single-transfer limit")
        sid = "S-%d" % self.state["next_sched"]
        self.state["next_sched"] += 1
        self.state["scheduled"][sid] = {"from": a["from_account"], "payee": a["payee_id"], "amount": a["amount"],
                                        "date": a["date"], "status": "pending"}
        return {"ok": True, "scheduled_id": sid}

    def _t_cancel_scheduled(self, a):
        s = self.state["scheduled"].get(a["scheduled_id"])
        if s is None:
            raise _Rule("unknown scheduled payment '%s'" % a["scheduled_id"][:30])
        if s["status"] != "pending":
            raise _Rule("scheduled payment %s is %s, not pending" % (a["scheduled_id"], s["status"]))
        s["status"] = "cancelled"
        return {"ok": True, "scheduled_id": a["scheduled_id"], "status": "cancelled"}

    def _t_close_account(self, a):
        aid = a["account_id"]
        ac = self._acct(aid, True)
        if ac["balance"] != 0:
            raise _Rule("cannot close %s: balance is %d, must be 0" % (aid, ac["balance"]))
        n = len([1 for h in self.state["holds"].values() if h["account"] == aid and h["status"] == "active"])
        if n:
            raise _Rule("cannot close %s: it has %d active hold(s)" % (aid, n))
        n = len([1 for s in self.state["scheduled"].values() if s["from"] == aid and s["status"] == "pending"])
        if n:
            raise _Rule("cannot close %s: it has %d pending scheduled payment(s)" % (aid, n))
        ac["status"] = "closed"
        return {"ok": True, "account_id": aid, "status": "closed"}


# --------------------------------------------------------------------------
# 2. deploy pipeline: services, builds, environments, approvals, rollbacks
# --------------------------------------------------------------------------
_ENVS3 = ["dev", "staging", "prod"]
_APPROVER_ROLES = ("approver", "release_manager")


def _ver(v):
    return tuple(int(x) for x in v.split("."))


class DeployEnv(_Env):
    TOOLS = [
        _fn("get_pipeline_info", "Today's date, the freeze status of each environment and the release policy "
            "(the rules that deploy, rollback, approve and quarantine enforce)."),
        _fn("list_services", "All services with their tier and owning team."),
        _fn("get_service", "One service: tier, the version and build deployed in each environment, the earlier versions "
            "each environment can roll back to, and which deployed builds of other services require this service.",
            {"service": _s("Service name, e.g. checkout.")}, ["service"]),
        _fn("list_users", "Pipeline users with their CURRENT role.",
            {"role": _s("Only users with this role.", ["dev", "approver", "release_manager"])}),
        _fn("list_builds", "Builds, newest first, 6 per page. All filters are optional and combine with AND.",
            {"service": _s("Only builds of this service."),
             "status": _s("Only builds with this CI status.", ["passed", "failed", "running"]),
             "author_id": _s("Only builds authored by this user id."),
             "approved_by": _s("Only builds that carry an approval from this user id."),
             "quarantined": _b("true: only quarantined builds; false: only builds that are not quarantined."),
             "page": _PAGE}),
        _fn("get_build", "One build in detail: service, version, CI status, security scan, author, creation date, "
            "minimum versions of other services it requires, approvals, quarantine flag, environments it is live in.",
            {"build_id": _s("Build id, e.g. B-123.")}, ["build_id"]),
        _fn("get_environment", "What is deployed in one environment: per service the version, its build id and the "
            "earlier versions it can be rolled back to (most recent last).",
            {"env": _s("Environment.", _ENVS3)}, ["env"]),
        _fn("deploy", "Deploy a build to an environment (replaces the service's current version there).",
            {"build_id": _s("Build id."), "env": _s("Target environment.", _ENVS3)}, ["build_id", "env"]),
        _fn("rollback", "Roll one service in one environment back ONE step, to the version it ran before the current one.",
            {"service": _s("Service name."), "env": _s("Environment.", _ENVS3)}, ["service", "env"]),
        _fn("approve_build", "Record a production approval for a build on behalf of a user.",
            {"build_id": _s("Build id."), "approver_id": _s("User id of the approver, e.g. U-02.")},
            ["build_id", "approver_id"]),
        _fn("revoke_approval", "Remove one user's approval from a build.",
            {"build_id": _s("Build id."), "approver_id": _s("User id whose approval is removed.")},
            ["build_id", "approver_id"]),
        _fn("quarantine_build", "Quarantine a build so that it can never be deployed again.",
            {"build_id": _s("Build id.")}, ["build_id"]),
        _fn("set_freeze", "Turn the deploy freeze of an environment on or off.",
            {"env": _s("Environment.", _ENVS3), "frozen": _b("true = frozen.")}, ["env", "frozen"]),
    ]

    def _build(self, bid):
        b = self.state["builds"].get(bid)
        if b is None:
            raise _Rule("unknown build '%s'" % bid[:30])
        return b

    def _svc(self, name):
        if name not in self.state["services"]:
            raise _Rule("unknown service '%s' (services: %s)" % (name[:30], ", ".join(sorted(self.state["services"]))))
        return self.state["services"][name]

    def _bid(self, service, version):
        for k, b in sorted(self.state["builds"].items()):
            if b["service"] == service and b["version"] == version:
                return k
        return None

    def _live_in(self, bid):
        b = self.state["builds"][bid]
        return [e for e in _ENVS3 if self.state["environments"][e]["deployed"].get(b["service"]) == b["version"]]

    def _valid_approvals(self, b):
        return [u for u in b["approvals"] if self.state["users"][u]["role"] in _APPROVER_ROLES]

    def _t_get_pipeline_info(self, a):
        return {"today": self.state["today"],
                "environments": [{"env": e, "frozen": self.state["environments"][e]["frozen"]} for e in _ENVS3],
                "policy": [
                    "Only builds with CI status 'passed' that are not quarantined can be deployed.",
                    "Promotion order: a build can go to staging only while it is the version currently deployed on dev, "
                    "and to prod only while it is the version currently deployed on staging.",
                    "deploy never downgrades: to go back to an older version use rollback.",
                    "Dependencies: a build can be deployed to an environment only if every service it requires is "
                    "already deployed there at the required minimum version or newer.",
                    "prod additionally requires: environment not frozen, security scan 'clean', and approvals - "
                    "standard-tier services need at least 1 valid approval; critical-tier services need at least 2 "
                    "valid approvals of which at least one is from a release_manager.",
                    "An approval is valid only while the approving user's CURRENT role is approver or release_manager. "
                    "Approvals from users who have since moved to another role stay on the build but do not count.",
                    "Approving: only users whose current role is approver or release_manager can approve, nobody can "
                    "approve their own build, and only passed builds with a clean scan can be approved.",
                    "rollback goes back one step and is allowed during a freeze. It is refused if another service "
                    "currently deployed in that environment requires a newer version than the rollback target.",
                    "A build that is live on staging or prod cannot be quarantined (being live on dev does not matter).",
                ]}

    def _t_list_services(self, a):
        return {"services": [{"service": k, "tier": v["tier"], "owner_team": v["team"]}
                             for k, v in sorted(self.state["services"].items())]}

    def _t_get_service(self, a):
        name = a["service"]
        sv = self._svc(name)
        envs, req = [], []
        for e in _ENVS3:
            env = self.state["environments"][e]
            v = env["deployed"][name]
            envs.append({"env": e, "version": v, "build_id": self._bid(name, v),
                         "can_roll_back_to": list(env["previous"][name])})
            for s2, v2 in sorted(env["deployed"].items()):
                b2 = self.state["builds"][self._bid(s2, v2)]
                if name in b2["requires"]:
                    req.append({"env": e, "service": s2, "version": v2, "requires_at_least": b2["requires"][name]})
        return {"service": name, "tier": sv["tier"], "owner_team": sv["team"], "deployed": envs, "required_by": req}

    def _t_list_users(self, a):
        return {"users": [{"user_id": k, "name": v["name"], "role": v["role"], "team": v["team"]}
                          for k, v in sorted(self.state["users"].items())
                          if "role" not in a or v["role"] == a["role"]]}

    def _t_list_builds(self, a):
        if "service" in a:
            self._svc(a["service"])
        for key in ("author_id", "approved_by"):
            if key in a and a[key] not in self.state["users"]:
                raise _Rule("unknown user '%s'" % a[key][:30])
        rows = []
        for k, b in self.state["builds"].items():
            if "service" in a and b["service"] != a["service"]:
                continue
            if "status" in a and b["status"] != a["status"]:
                continue
            if "author_id" in a and b["author"] != a["author_id"]:
                continue
            if "approved_by" in a and a["approved_by"] not in b["approvals"]:
                continue
            if "quarantined" in a and b["quarantined"] != a["quarantined"]:
                continue
            rows.append((b["created"], k, b))
        rows.sort(reverse=True)
        meta, rows = _paged(rows, a.get("page", 1), 6)
        meta["builds"] = [{"build_id": k, "service": b["service"], "version": b["version"], "status": b["status"],
                           "scan": b["scan"], "author_id": b["author"], "created": d,
                           "approvals": len(b["approvals"]), "quarantined": b["quarantined"]} for d, k, b in rows]
        return meta

    def _t_get_build(self, a):
        b = self._build(a["build_id"])
        return {"build_id": a["build_id"], "service": b["service"], "version": b["version"], "status": b["status"],
                "scan": b["scan"], "author_id": b["author"], "author_name": self.state["users"][b["author"]]["name"],
                "created": b["created"],
                "requires": [{"service": s, "min_version": v} for s, v in sorted(b["requires"].items())],
                "approvals": [{"user_id": u, "name": self.state["users"][u]["name"]} for u in b["approvals"]],
                "quarantined": b["quarantined"], "live_in": self._live_in(a["build_id"])}

    def _t_get_environment(self, a):
        env = self.state["environments"][a["env"]]
        return {"env": a["env"], "frozen": env["frozen"],
                "services": [{"service": s, "version": v, "build_id": self._bid(s, v),
                              "can_roll_back_to": list(env["previous"][s])}
                             for s, v in sorted(env["deployed"].items())]}

    def _t_deploy(self, a):
        bid, e = a["build_id"], a["env"]
        b = self._build(bid)
        env = self.state["environments"][e]
        svc, v = b["service"], b["version"]
        if b["status"] != "passed":
            raise _Rule("build %s has CI status '%s'; only passed builds can be deployed" % (bid, b["status"]))
        if b["quarantined"]:
            raise _Rule("build %s is quarantined" % bid)
        cur = env["deployed"][svc]
        if v == cur:
            raise _Rule("%s %s is already the version deployed on %s" % (svc, v, e))
        if _ver(v) < _ver(cur):
            raise _Rule("%s on %s is at %s; deploy cannot downgrade to %s - use rollback" % (svc, e, cur, v))
        if e != "dev":
            before = _ENVS3[_ENVS3.index(e) - 1]
            if self.state["environments"][before]["deployed"][svc] != v:
                raise _Rule("%s %s must be the version currently deployed on %s before it can go to %s (%s has %s)" % (
                    svc, v, before, e, before, self.state["environments"][before]["deployed"][svc]))
        if e == "prod":
            if env["frozen"]:
                raise _Rule("prod is frozen; no deploys")
            if b["scan"] != "clean":
                raise _Rule("build %s has security scan '%s'; prod requires 'clean'" % (bid, b["scan"]))
            valid = self._valid_approvals(b)
            if self.state["services"][svc]["tier"] == "critical":
                rm = [u for u in valid if self.state["users"][u]["role"] == "release_manager"]
                if len(valid) < 2 or not rm:
                    raise _Rule("%s is critical: prod needs 2 valid approvals incl. one release_manager; build %s has "
                                "%d valid approval(s), %d from a release_manager" % (svc, bid, len(valid), len(rm)))
            elif len(valid) < 1:
                raise _Rule("prod needs 1 valid approval; build %s has none that count" % bid)
        for s2, minv in sorted(b["requires"].items()):
            have = env["deployed"][s2]
            if _ver(have) < _ver(minv):
                raise _Rule("%s %s requires %s >= %s on %s, but %s has %s %s" % (svc, v, s2, minv, e, e, s2, have))
        env["previous"][svc].append(cur)
        env["deployed"][svc] = v
        return {"ok": True, "env": e, "service": svc, "version": v, "replaced": cur}

    def _t_rollback(self, a):
        svc, e = a["service"], a["env"]
        self._svc(svc)
        env = self.state["environments"][e]
        if not env["previous"][svc]:
            raise _Rule("%s on %s has no earlier version to roll back to" % (svc, e))
        target = env["previous"][svc][-1]
        for s2, v2 in sorted(env["deployed"].items()):
            if s2 == svc:
                continue
            need = self.state["builds"][self._bid(s2, v2)]["requires"].get(svc)
            if need and _ver(need) > _ver(target):
                raise _Rule("cannot roll %s back to %s on %s: %s %s (deployed on %s) requires %s >= %s" % (
                    svc, target, e, s2, v2, e, svc, need))
        cur = env["deployed"][svc]
        env["previous"][svc].pop()
        env["deployed"][svc] = target
        return {"ok": True, "env": e, "service": svc, "version": target, "rolled_back_from": cur}

    def _t_approve_build(self, a):
        b = self._build(a["build_id"])
        u = self.state["users"].get(a["approver_id"])
        if u is None:
            raise _Rule("unknown user '%s'" % a["approver_id"][:30])
        if u["role"] not in _APPROVER_ROLES:
            raise _Rule("%s has role '%s' and cannot approve builds" % (u["name"], u["role"]))
        if b["author"] == a["approver_id"]:
            raise _Rule("%s is the author of %s and cannot approve it" % (u["name"], a["build_id"]))
        if b["status"] != "passed" or b["scan"] != "clean":
            raise _Rule("only passed builds with a clean scan can be approved (status %s, scan %s)" % (b["status"], b["scan"]))
        if a["approver_id"] in b["approvals"]:
            raise _Rule("%s has already approved %s" % (u["name"], a["build_id"]))
        b["approvals"].append(a["approver_id"])
        return {"ok": True, "build_id": a["build_id"], "approvals": list(b["approvals"])}

    def _t_revoke_approval(self, a):
        b = self._build(a["build_id"])
        if a["approver_id"] not in b["approvals"]:
            raise _Rule("build %s has no approval from '%s'" % (a["build_id"], a["approver_id"][:30]))
        b["approvals"].remove(a["approver_id"])
        return {"ok": True, "build_id": a["build_id"], "approvals": list(b["approvals"])}

    def _t_quarantine_build(self, a):
        b = self._build(a["build_id"])
        if b["quarantined"]:
            raise _Rule("build %s is already quarantined" % a["build_id"])
        live = [e for e in self._live_in(a["build_id"]) if e != "dev"]
        if live:
            raise _Rule("build %s (%s %s) is live on %s and cannot be quarantined while it is" % (
                a["build_id"], b["service"], b["version"], " and ".join(live)))
        b["quarantined"] = True
        return {"ok": True, "build_id": a["build_id"], "quarantined": True}

    def _t_set_freeze(self, a):
        env = self.state["environments"][a["env"]]
        if env["frozen"] == a["frozen"]:
            raise _Rule("%s is already %s" % (a["env"], "frozen" if a["frozen"] else "not frozen"))
        env["frozen"] = a["frozen"]
        return {"ok": True, "env": a["env"], "frozen": a["frozen"]}


# --------------------------------------------------------------------------
# 3. registrar: students, sections, prerequisites, capacities, waitlists
# --------------------------------------------------------------------------
_WEEK = ["mon", "tue", "wed", "thu", "fri"]


class RegistrarEnv(_Env):
    TOOLS = [
        _fn("get_term_info", "Today's date, the term, the registration policy (rules the write tools enforce), "
            "the course catalogue (credits, prerequisites) and the rooms with their capacities."),
        _fn("find_students", "Search students by name (case-insensitive substring).",
            {"query": _s("Text that must appear in the student's name.")}, ["query"]),
        _fn("get_student", "One student: year, department, registration holds, past grades, current sections "
            "with meeting times, total enrolled credits, waitlist positions.",
            {"student_id": _s("Student id, e.g. S-06.")}, ["student_id"]),
        _fn("list_sections", "Sections this term, 6 per page, ordered by section id: course, days, times, room, "
            "capacity, number enrolled, free seats, waitlist length, status.",
            {"course_id": _s("Only sections of this course, e.g. MATH220."),
             "day": _s("Only sections that meet on this weekday.", _WEEK),
             "page": _PAGE}),
        _fn("get_section", "One section in detail, with its roster and its waitlist in order (position 1 is first in line).",
            {"section_id": _s("Section id, e.g. MATH220-A.")}, ["section_id"]),
        _fn("list_grades", "Past grades recorded for one course (one row per student who has a record), 8 per page.",
            {"course_id": _s("Course id, e.g. CHEM110."), "page": _PAGE}, ["course_id"]),
        _fn("enroll", "Enroll a student in a section. If the student was on that section's waitlist the waitlist entry is removed.",
            {"student_id": _s("Student id."), "section_id": _s("Section id.")}, ["student_id", "section_id"]),
        _fn("drop", "Drop a student from a section they are enrolled in. Nobody is moved up from the waitlist automatically.",
            {"student_id": _s("Student id."), "section_id": _s("Section id.")}, ["student_id", "section_id"]),
        _fn("swap_section", "Move an enrolled student from one section to another section of the SAME course in one step.",
            {"student_id": _s("Student id."), "from_section": _s("Section the student is in now."),
             "to_section": _s("Section to move to.")}, ["student_id", "from_section", "to_section"]),
        _fn("join_waitlist", "Add a student to the end of a full section's waitlist.",
            {"student_id": _s("Student id."), "section_id": _s("Section id.")}, ["student_id", "section_id"]),
        _fn("leave_waitlist", "Remove a student from a section's waitlist.",
            {"student_id": _s("Student id."), "section_id": _s("Section id.")}, ["student_id", "section_id"]),
        _fn("set_capacity", "Change the capacity (number of seats) of a section.",
            {"section_id": _s("Section id."), "capacity": _i("New capacity.", 0)}, ["section_id", "capacity"]),
        _fn("change_room", "Move a section to a different room (same days and times).",
            {"section_id": _s("Section id."), "room_id": _s("Room id, e.g. R-201.")}, ["section_id", "room_id"]),
        _fn("cancel_section", "Cancel a section for this term.", {"section_id": _s("Section id.")}, ["section_id"]),
    ]

    def _stu(self, sid):
        s = self.state["students"].get(sid)
        if s is None:
            raise _Rule("unknown student '%s'" % sid[:30])
        return s

    def _sec(self, sec, must_open=True):
        s = self.state["sections"].get(sec)
        if s is None:
            raise _Rule("unknown section '%s'" % sec[:30])
        if must_open and s["status"] != "open":
            raise _Rule("section %s is cancelled" % sec)
        return s

    def _mine(self, sid):
        return [k for k, s in sorted(self.state["sections"].items()) if s["status"] == "open" and sid in s["enrolled"]]

    def _credits(self, sid):
        return sum(self.state["courses"][self.state["sections"][k]["course"]]["credits"] for k in self._mine(sid))

    @staticmethod
    def _overlap(x, y):
        return bool(set(x["days"]) & set(y["days"])) and \
            _ptime(x["start"]) < _ptime(y["end"]) and _ptime(y["start"]) < _ptime(x["end"])

    def _clash(self, sid, sec_id, ignore=None):
        tgt = self.state["sections"][sec_id]
        for k in self._mine(sid):
            if k != ignore and k != sec_id and self._overlap(self.state["sections"][k], tgt):
                return k
        return None

    def _times(self, s):
        return {"days": list(s["days"]), "start": s["start"], "end": s["end"]}

    def _t_get_term_info(self, a):
        st = self.state
        ok = ", ".join(st["policy"]["passing"])
        return {"today": st["today"], "term": st["term"], "policy": {
            "max_credits": st["policy"]["max_credits"],
            "rules": [
                "A prerequisite counts as met only with one of these grades in the prerequisite course: %s. "
                "Anything else (C-, D+, D, F, W = withdrawn, I = incomplete) or no record does not count." % ok,
                "A student may be enrolled in at most max_credits credits. Waitlisted courses do not count.",
                "A student cannot be enrolled in two sections whose meeting times overlap, nor in two sections of the same course.",
                "Students with a 'financial' hold cannot enroll or join waitlists.",
                "Waitlists exist only on full sections. Dropping a student never moves anyone up automatically; "
                "staff enroll the next person from the waitlist by hand.",
                "A section's capacity cannot exceed the capacity of its room, and a room can host only one section at a time.",
                "A section can be cancelled only once it has no enrolled students and an empty waitlist.",
            ]},
            "courses": [{"course_id": k, "title": c["title"], "credits": c["credits"], "department": c["dept"],
                         "prerequisites": list(c["prereqs"])} for k, c in sorted(st["courses"].items())],
            "rooms": [{"room_id": k, "capacity": v} for k, v in sorted(st["rooms"].items())]}

    def _t_find_students(self, a):
        q = a["query"].strip().lower()
        return {"students": [{"student_id": k, "name": v["name"], "year": v["year"], "department": v["dept"]}
                             for k, v in sorted(self.state["students"].items()) if q in v["name"].lower()][:12]}

    def _t_get_student(self, a):
        sid = a["student_id"]
        s = self._stu(sid)
        secs = self.state["sections"]
        enrolled = []
        for k in self._mine(sid):
            row = {"section_id": k, "course_id": secs[k]["course"],
                   "credits": self.state["courses"][secs[k]["course"]]["credits"]}
            row.update(self._times(secs[k]))
            enrolled.append(row)
        wl = [{"section_id": k, "position": v["waitlist"].index(sid) + 1}
              for k, v in sorted(secs.items()) if sid in v["waitlist"]]
        return {"student_id": sid, "name": s["name"], "year": s["year"], "department": s["dept"],
                "holds": list(s["holds"]),
                "past_grades": [{"course_id": c, "grade": g} for c, g in sorted(s["completed"].items())],
                "enrolled": enrolled, "enrolled_credits": self._credits(sid), "waitlisted": wl}

    def _row(self, k):
        s = self.state["sections"][k]
        row = {"section_id": k, "course_id": s["course"], "credits": self.state["courses"][s["course"]]["credits"]}
        row.update(self._times(s))
        row.update({"room_id": s["room"], "capacity": s["capacity"], "enrolled": len(s["enrolled"]),
                    "seats_free": max(0, s["capacity"] - len(s["enrolled"])), "waitlist": len(s["waitlist"]),
                    "status": s["status"]})
        return row

    def _t_list_sections(self, a):
        if "course_id" in a and a["course_id"] not in self.state["courses"]:
            raise _Rule("unknown course '%s'" % a["course_id"][:30])
        keys = [k for k, s in sorted(self.state["sections"].items())
                if ("course_id" not in a or s["course"] == a["course_id"]) and ("day" not in a or a["day"] in s["days"])]
        meta, keys = _paged(keys, a.get("page", 1), 6)
        meta["sections"] = [self._row(k) for k in keys]
        return meta

    def _t_get_section(self, a):
        k = a["section_id"]
        s = self._sec(k, False)
        st = self.state["students"]
        row = self._row(k)
        row["title"] = self.state["courses"][s["course"]]["title"]
        row["room_capacity"] = self.state["rooms"][s["room"]]
        row["roster"] = [{"student_id": x, "name": st[x]["name"], "year": st[x]["year"]} for x in sorted(s["enrolled"])]
        row["waitlist"] = [{"position": n + 1, "student_id": x, "name": st[x]["name"], "year": st[x]["year"]}
                           for n, x in enumerate(s["waitlist"])]
        return row

    def _t_list_grades(self, a):
        c = a["course_id"]
        if c not in self.state["courses"]:
            raise _Rule("unknown course '%s'" % c[:30])
        rows = [{"student_id": k, "name": v["name"], "grade": v["completed"][c]}
                for k, v in sorted(self.state["students"].items()) if c in v["completed"]]
        meta, rows = _paged(rows, a.get("page", 1), 8)
        meta["course_id"] = c
        meta["grades"] = rows
        return meta

    def _prereq_gap(self, sid, course):
        s = self.state["students"][sid]
        for p in self.state["courses"][course]["prereqs"]:
            if s["completed"].get(p) not in self.state["policy"]["passing"]:
                return p
        return None

    def _t_enroll(self, a):
        sid, k = a["student_id"], a["section_id"]
        stu = self._stu(sid)
        sec = self._sec(k)
        course = sec["course"]
        if "financial" in stu["holds"]:
            raise _Rule("%s has a financial hold and cannot enroll" % sid)
        for m in self._mine(sid):
            if self.state["sections"][m]["course"] == course:
                raise _Rule("%s is already enrolled in %s (section %s)" % (sid, course, m))
        gap = self._prereq_gap(sid, course)
        if gap:
            raise _Rule("%s does not meet the prerequisite %s for %s (grade on record: %s)" % (
                sid, gap, course, stu["completed"].get(gap, "none")))
        c = self._clash(sid, k)
        if c:
            raise _Rule("time clash: %s overlaps with %s, which %s is enrolled in" % (k, c, sid))
        if len(sec["enrolled"]) >= sec["capacity"]:
            raise _Rule("section %s is full (%d/%d)" % (k, len(sec["enrolled"]), sec["capacity"]))
        cr = self.state["courses"][course]["credits"]
        if self._credits(sid) + cr > self.state["policy"]["max_credits"]:
            raise _Rule("credit limit: %s has %d credits; adding %d would exceed the maximum of %d" % (
                sid, self._credits(sid), cr, self.state["policy"]["max_credits"]))
        sec["enrolled"].append(sid)
        if sid in sec["waitlist"]:
            sec["waitlist"].remove(sid)
        return {"ok": True, "student_id": sid, "section_id": k, "enrolled_credits": self._credits(sid),
                "seats_free": sec["capacity"] - len(sec["enrolled"])}

    def _t_drop(self, a):
        sid, k = a["student_id"], a["section_id"]
        self._stu(sid)
        sec = self._sec(k)
        if sid not in sec["enrolled"]:
            raise _Rule("%s is not enrolled in %s" % (sid, k))
        sec["enrolled"].remove(sid)
        return {"ok": True, "student_id": sid, "section_id": k, "seats_free": max(0, sec["capacity"] - len(sec["enrolled"])),
                "waitlist": len(sec["waitlist"])}

    def _t_swap_section(self, a):
        sid, f, t = a["student_id"], a["from_section"], a["to_section"]
        self._stu(sid)
        src = self._sec(f)
        dst = self._sec(t)
        if f == t:
            raise _Rule("from_section and to_section are the same")
        if src["course"] != dst["course"]:
            raise _Rule("%s and %s are not sections of the same course" % (f, t))
        if sid not in src["enrolled"]:
            raise _Rule("%s is not enrolled in %s" % (sid, f))
        c = self._clash(sid, t, ignore=f)
        if c:
            raise _Rule("time clash: %s overlaps with %s, which %s is enrolled in" % (t, c, sid))
        if len(dst["enrolled"]) >= dst["capacity"]:
            raise _Rule("section %s is full (%d/%d)" % (t, len(dst["enrolled"]), dst["capacity"]))
        src["enrolled"].remove(sid)
        dst["enrolled"].append(sid)
        if sid in dst["waitlist"]:
            dst["waitlist"].remove(sid)
        return {"ok": True, "student_id": sid, "now_in": t, "seats_free_in_target": dst["capacity"] - len(dst["enrolled"])}

    def _t_join_waitlist(self, a):
        sid, k = a["student_id"], a["section_id"]
        stu = self._stu(sid)
        sec = self._sec(k)
        if "financial" in stu["holds"]:
            raise _Rule("%s has a financial hold and cannot join waitlists" % sid)
        if len(sec["enrolled"]) < sec["capacity"]:
            raise _Rule("section %s is not full (%d/%d); waitlists exist only on full sections" % (
                k, len(sec["enrolled"]), sec["capacity"]))
        for m in self._mine(sid):
            if self.state["sections"][m]["course"] == sec["course"]:
                raise _Rule("%s is already enrolled in %s (section %s)" % (sid, sec["course"], m))
        if sid in sec["waitlist"]:
            raise _Rule("%s is already on the waitlist of %s" % (sid, k))
        sec["waitlist"].append(sid)
        return {"ok": True, "student_id": sid, "section_id": k, "position": len(sec["waitlist"])}

    def _t_leave_waitlist(self, a):
        sid, k = a["student_id"], a["section_id"]
        self._stu(sid)
        sec = self._sec(k)
        if sid not in sec["waitlist"]:
            raise _Rule("%s is not on the waitlist of %s" % (sid, k))
        sec["waitlist"].remove(sid)
        return {"ok": True, "student_id": sid, "section_id": k, "waitlist": len(sec["waitlist"])}

    def _t_set_capacity(self, a):
        k = a["section_id"]
        sec = self._sec(k)
        if a["capacity"] < len(sec["enrolled"]):
            raise _Rule("capacity %d is below the %d students enrolled in %s" % (a["capacity"], len(sec["enrolled"]), k))
        rc = self.state["rooms"][sec["room"]]
        if a["capacity"] > rc:
            raise _Rule("capacity %d exceeds room %s, which holds %d" % (a["capacity"], sec["room"], rc))
        if a["capacity"] == sec["capacity"]:
            raise _Rule("capacity of %s is already %d" % (k, a["capacity"]))
        sec["capacity"] = a["capacity"]
        return {"ok": True, "section_id": k, "capacity": sec["capacity"], "seats_free": sec["capacity"] - len(sec["enrolled"])}

    def _t_change_room(self, a):
        k, r = a["section_id"], a["room_id"]
        sec = self._sec(k)
        if r not in self.state["rooms"]:
            raise _Rule("unknown room '%s'" % r[:30])
        if r == sec["room"]:
            raise _Rule("%s is already in room %s" % (k, r))
        if self.state["rooms"][r] < sec["capacity"]:
            raise _Rule("room %s holds %d, fewer than the section capacity %d" % (r, self.state["rooms"][r], sec["capacity"]))
        for k2, s2 in sorted(self.state["sections"].items()):
            if k2 != k and s2["status"] == "open" and s2["room"] == r and self._overlap(s2, sec):
                raise _Rule("room %s is occupied by %s (%s %s-%s) at that time" % (
                    r, k2, "/".join(s2["days"]), s2["start"], s2["end"]))
        sec["room"] = r
        return {"ok": True, "section_id": k, "room_id": r, "room_capacity": self.state["rooms"][r]}

    def _t_cancel_section(self, a):
        k = a["section_id"]
        sec = self._sec(k)
        if sec["enrolled"] or sec["waitlist"]:
            raise _Rule("cannot cancel %s: %d enrolled, %d on the waitlist" % (k, len(sec["enrolled"]), len(sec["waitlist"])))
        sec["status"] = "cancelled"
        return {"ok": True, "section_id": k, "status": "cancelled"}


# --------------------------------------------------------------------------
# 4. fleet dispatch: vehicles, drivers, jobs, maintenance windows
# --------------------------------------------------------------------------
_LIC = {"B": 1, "C": 2, "CE": 3}
_VNEED = {"van": "B", "box_truck": "C", "reefer": "C", "flatbed": "CE"}
_VTYPES = ["van", "box_truck", "reefer", "flatbed"]
_PRIOS = ["low", "normal", "high", "urgent"]
_MKINDS = ["service", "inspection", "repair", "decommission"]


class FleetEnv(_Env):
    TOOLS = [
        _fn("get_dispatch_info", "Today's date and weekday, the depots, and the dispatch policy (rules that assign_job "
            "and the other write tools enforce)."),
        _fn("list_vehicles", "Vehicles with type, payload capacity, depot, status, odometer and odometer at last service.",
            {"depot": _s("Only vehicles based at this depot."), "type": _s("Only vehicles of this type.", _VTYPES)}),
        _fn("get_vehicle", "One vehicle in detail, with its assigned jobs from today onwards and its scheduled maintenance windows.",
            {"vehicle_id": _s("Vehicle id, e.g. V-04.")}, ["vehicle_id"]),
        _fn("list_drivers", "Drivers with licence class, certificates, depot and status.",
            {"depot": _s("Only drivers based at this depot.")}),
        _fn("get_driver", "One driver in detail, with their assigned jobs from today onwards and job hours per date.",
            {"driver_id": _s("Driver id, e.g. D-01.")}, ["driver_id"]),
        _fn("list_jobs", "Jobs ordered by date and start hour, 8 per page. All filters are optional and combine with AND.",
            {"date": _s("Only jobs on this date, YYYY-MM-DD."), "depot": _s("Only jobs of this depot."),
             "status": _s("Only jobs in this status.", ["unassigned", "assigned", "cancelled", "done"]),
             "page": _PAGE}),
        _fn("get_job", "One job in detail.", {"job_id": _s("Job id, e.g. J-101.")}, ["job_id"]),
        _fn("create_job", "Create a new unassigned job.",
            {"date": _s("Date, YYYY-MM-DD."), "start_hour": _i("Start hour, 0-23.", 0, 23),
             "end_hour": _i("End hour, 1-24, after start_hour.", 1, 24), "depot": _s("Depot that runs the job."),
             "customer": _s("Customer name."), "load_kg": _i("Load in kg.", 1),
             "requires": _s("Special requirement.", ["none", "reefer", "hazmat"]),
             "priority": _s("Priority.", _PRIOS)},
            ["date", "start_hour", "end_hour", "depot", "customer", "load_kg", "requires", "priority"]),
        _fn("assign_job", "Assign an unassigned job to a vehicle and a driver.",
            {"job_id": _s("Job id."), "vehicle_id": _s("Vehicle id."), "driver_id": _s("Driver id.")},
            ["job_id", "vehicle_id", "driver_id"]),
        _fn("unassign_job", "Remove vehicle and driver from an assigned job (it becomes unassigned).",
            {"job_id": _s("Job id.")}, ["job_id"]),
        _fn("reschedule_job", "Move an unassigned job to another date and/or start hour; its duration is kept.",
            {"job_id": _s("Job id."), "date": _s("New date, YYYY-MM-DD."), "start_hour": _i("New start hour, 0-23.", 0, 23)},
            ["job_id", "date", "start_hour"]),
        _fn("cancel_job", "Cancel a job (any vehicle/driver assignment is removed).", {"job_id": _s("Job id.")}, ["job_id"]),
        _fn("schedule_maintenance", "Book a maintenance window for a vehicle.",
            {"vehicle_id": _s("Vehicle id."), "date": _s("Date, YYYY-MM-DD."), "start_hour": _i("Start hour, 0-23.", 0, 23),
             "duration_hours": _i("Length in hours.", 1, 24), "kind": _s("Kind of work.", _MKINDS)},
            ["vehicle_id", "date", "start_hour", "duration_hours", "kind"]),
        _fn("set_vehicle_status", "Set a vehicle active or out of service.",
            {"vehicle_id": _s("Vehicle id."), "status": _s("New status.", ["active", "out_of_service"])},
            ["vehicle_id", "status"]),
    ]

    def _veh(self, vid):
        v = self.state["vehicles"].get(vid)
        if v is None:
            raise _Rule("unknown vehicle '%s'" % vid[:30])
        return v

    def _drv(self, did):
        d = self.state["drivers"].get(did)
        if d is None:
            raise _Rule("unknown driver '%s'" % did[:30])
        return d

    def _job(self, jid):
        j = self.state["jobs"].get(jid)
        if j is None:
            raise _Rule("unknown job '%s'" % jid[:30])
        return j

    def _depot(self, d):
        if d not in self.state["depots"]:
            raise _Rule("unknown depot '%s' (depots: %s)" % (d[:30], ", ".join(self.state["depots"])))

    def _jview(self, k):
        j = self.state["jobs"][k]
        return {"job_id": k, "date": j["date"], "start_hour": j["start"], "end_hour": j["end"], "depot": j["depot"],
                "customer": j["customer"], "load_kg": j["load_kg"], "requires": j["requires"], "priority": j["priority"],
                "status": j["status"], "vehicle_id": j["vehicle"], "driver_id": j["driver"]}

    def _jobs_of(self, key, ident, date=None):
        out = [(j["date"], j["start"], k) for k, j in self.state["jobs"].items()
               if j["status"] == "assigned" and j[key] == ident and (date is None or j["date"] == date)]
        return [k for _, _, k in sorted(out)]

    def _t_get_dispatch_info(self, a):
        st = self.state
        d = _pdate(st["today"])
        return {"today": st["today"], "weekday": _DAYNAMES[d.weekday()], "depots": list(st["depots"]), "policy": {
            "max_driver_job_hours_per_day": st["policy"]["max_daily_hours"],
            "service_interval_km": st["policy"]["service_interval_km"],
            "rules": [
                "A job can only be assigned to a vehicle and a driver of the job's own depot; both must be active "
                "(vehicle not out_of_service, driver not on_leave).",
                "Licence classes B < C < CE; a higher class covers the lower ones. van needs B, box_truck and reefer need C, flatbed needs CE.",
                "The vehicle's capacity_kg must be at least the job's load_kg.",
                "Jobs that require 'reefer' need a reefer vehicle and a driver with the cold_chain certificate. "
                "Jobs that require 'hazmat' need a driver with the hazmat certificate and may not go on a van. "
                "Jobs with requirement 'none' may use any vehicle type.",
                "A vehicle or a driver cannot have two jobs that overlap in time; a vehicle cannot work during one of its "
                "scheduled maintenance windows. A job ending at hour N does not overlap one starting at hour N.",
                "A driver's assigned job hours on one date may not exceed max_driver_job_hours_per_day.",
                "A vehicle that has driven service_interval_km or more since its last service (odometer_km - "
                "last_service_km) is due for service and cannot be given NEW assignments; existing ones stay.",
                "An assigned job must be unassigned before it can be rescheduled or given to another vehicle/driver.",
                "A maintenance window cannot overlap an assigned job of that vehicle. A vehicle cannot be set "
                "out_of_service while it still has assigned jobs dated today or later.",
            ]}}

    def _t_list_vehicles(self, a):
        if "depot" in a:
            self._depot(a["depot"])
        out = []
        for k, v in sorted(self.state["vehicles"].items()):
            if ("depot" in a and v["depot"] != a["depot"]) or ("type" in a and v["type"] != a["type"]):
                continue
            out.append({"vehicle_id": k, "type": v["type"], "capacity_kg": v["capacity_kg"], "depot": v["depot"],
                        "status": v["status"], "odometer_km": v["odometer_km"], "last_service_km": v["last_service_km"]})
        return {"vehicles": out}

    def _t_get_vehicle(self, a):
        k = a["vehicle_id"]
        v = self._veh(k)
        jobs = [self._jview(j) for j in self._jobs_of("vehicle", k) if self.state["jobs"][j]["date"] >= self.state["today"]]
        maint = [{"maintenance_id": m, "date": x["date"], "start_hour": x["start"], "end_hour": x["end"], "kind": x["kind"]}
                 for m, x in sorted(self.state["maintenance"].items()) if x["vehicle"] == k]
        return {"vehicle_id": k, "type": v["type"], "capacity_kg": v["capacity_kg"], "depot": v["depot"],
                "status": v["status"], "odometer_km": v["odometer_km"], "last_service_km": v["last_service_km"],
                "assigned_jobs": jobs, "maintenance": maint}

    def _t_list_drivers(self, a):
        if "depot" in a:
            self._depot(a["depot"])
        return {"drivers": [{"driver_id": k, "name": d["name"], "licence": d["licence"], "certificates": list(d["certs"]),
                             "depot": d["depot"], "status": d["status"]}
                            for k, d in sorted(self.state["drivers"].items()) if "depot" not in a or d["depot"] == a["depot"]]}

    def _t_get_driver(self, a):
        k = a["driver_id"]
        d = self._drv(k)
        ids = [j for j in self._jobs_of("driver", k) if self.state["jobs"][j]["date"] >= self.state["today"]]
        hours = {}
        for j in ids:
            x = self.state["jobs"][j]
            hours[x["date"]] = hours.get(x["date"], 0) + x["end"] - x["start"]
        return {"driver_id": k, "name": d["name"], "licence": d["licence"], "certificates": list(d["certs"]),
                "depot": d["depot"], "status": d["status"], "assigned_jobs": [self._jview(j) for j in ids],
                "job_hours_by_date": [{"date": x, "hours": h} for x, h in sorted(hours.items())]}

    def _t_list_jobs(self, a):
        if "depot" in a:
            self._depot(a["depot"])
        if "date" in a:
            _pdate(a["date"])
        rows = []
        for k, j in self.state["jobs"].items():
            if ("date" in a and j["date"] != a["date"]) or ("depot" in a and j["depot"] != a["depot"]) or \
                    ("status" in a and j["status"] != a["status"]):
                continue
            rows.append((j["date"], j["start"], k))
        rows.sort()
        meta, rows = _paged(rows, a.get("page", 1), 8)
        meta["jobs"] = [self._jview(k) for _, _, k in rows]
        return meta

    def _t_get_job(self, a):
        self._job(a["job_id"])
        return self._jview(a["job_id"])

    def _future(self, date):
        if _pdate(date) < _pdate(self.state["today"]):
            raise _Rule("date %s is in the past (today is %s)" % (date, self.state["today"]))

    def _t_create_job(self, a):
        self._future(a["date"])
        self._depot(a["depot"])
        if a["end_hour"] <= a["start_hour"]:
            raise _Rule("end_hour must be after start_hour")
        if not a["customer"].strip():
            raise _Rule("customer must not be empty")
        jid = "J-%d" % self.state["next_job"]
        self.state["next_job"] += 1
        self.state["jobs"][jid] = {"date": a["date"], "start": a["start_hour"], "end": a["end_hour"], "depot": a["depot"],
                                   "customer": a["customer"].strip()[:60], "load_kg": a["load_kg"], "requires": a["requires"],
                                   "priority": a["priority"], "status": "unassigned", "vehicle": None, "driver": None}
        return {"ok": True, "job": self._jview(jid)}

    def _t_assign_job(self, a):
        jid, vid, did = a["job_id"], a["vehicle_id"], a["driver_id"]
        j, v, d = self._job(jid), self._veh(vid), self._drv(did)
        pol = self.state["policy"]
        if j["status"] == "assigned":
            raise _Rule("job %s is already assigned (%s, %s); unassign it first" % (jid, j["vehicle"], j["driver"]))
        if j["status"] != "unassigned":
            raise _Rule("job %s is %s" % (jid, j["status"]))
        if v["status"] != "active":
            raise _Rule("vehicle %s is out of service" % vid)
        if d["status"] != "active":
            raise _Rule("driver %s is on leave" % did)
        if v["depot"] != j["depot"]:
            raise _Rule("vehicle %s is based at %s, the job belongs to %s" % (vid, v["depot"], j["depot"]))
        if d["depot"] != j["depot"]:
            raise _Rule("driver %s is based at %s, the job belongs to %s" % (did, d["depot"], j["depot"]))
        if j["requires"] == "reefer":
            if v["type"] != "reefer":
                raise _Rule("job %s requires a reefer vehicle; %s is a %s" % (jid, vid, v["type"]))
            if "cold_chain" not in d["certs"]:
                raise _Rule("job %s requires a driver with the cold_chain certificate; %s does not have it" % (jid, did))
        if j["requires"] == "hazmat":
            if v["type"] == "van":
                raise _Rule("hazmat jobs may not go on a van")
            if "hazmat" not in d["certs"]:
                raise _Rule("job %s requires a driver with the hazmat certificate; %s does not have it" % (jid, did))
        if v["capacity_kg"] < j["load_kg"]:
            raise _Rule("vehicle %s carries %d kg, the job needs %d kg" % (vid, v["capacity_kg"], j["load_kg"]))
        if _LIC[d["licence"]] < _LIC[_VNEED[v["type"]]]:
            raise _Rule("driver %s has licence %s; a %s needs %s" % (did, d["licence"], v["type"], _VNEED[v["type"]]))
        if v["odometer_km"] - v["last_service_km"] >= pol["service_interval_km"]:
            raise _Rule("vehicle %s is due for service (%d km since last service) and cannot take new assignments" % (
                vid, v["odometer_km"] - v["last_service_km"]))
        for k in self._jobs_of("vehicle", vid, j["date"]):
            o = self.state["jobs"][k]
            if o["start"] < j["end"] and j["start"] < o["end"]:
                raise _Rule("vehicle %s is busy with %s (%02d-%02d) at that time" % (vid, k, o["start"], o["end"]))
        for m, x in sorted(self.state["maintenance"].items()):
            if x["vehicle"] == vid and x["date"] == j["date"] and x["start"] < j["end"] and j["start"] < x["end"]:
                raise _Rule("vehicle %s is in maintenance (%s, %02d-%02d) at that time" % (vid, x["kind"], x["start"], x["end"]))
        hours = j["end"] - j["start"]
        for k in self._jobs_of("driver", did, j["date"]):
            o = self.state["jobs"][k]
            if o["start"] < j["end"] and j["start"] < o["end"]:
                raise _Rule("driver %s is busy with %s (%02d-%02d) at that time" % (did, k, o["start"], o["end"]))
            hours += o["end"] - o["start"]
        if hours > pol["max_daily_hours"]:
            raise _Rule("driver %s would have %d job hours on %s; the maximum is %d" % (did, hours, j["date"], pol["max_daily_hours"]))
        j["status"], j["vehicle"], j["driver"] = "assigned", vid, did
        return {"ok": True, "job": self._jview(jid)}

    def _t_unassign_job(self, a):
        j = self._job(a["job_id"])
        if j["status"] != "assigned":
            raise _Rule("job %s is not assigned (status: %s)" % (a["job_id"], j["status"]))
        j["status"], j["vehicle"], j["driver"] = "unassigned", None, None
        return {"ok": True, "job": self._jview(a["job_id"])}

    def _t_reschedule_job(self, a):
        j = self._job(a["job_id"])
        if j["status"] == "assigned":
            raise _Rule("job %s is assigned; unassign it before rescheduling" % a["job_id"])
        if j["status"] != "unassigned":
            raise _Rule("job %s is %s" % (a["job_id"], j["status"]))
        self._future(a["date"])
        dur = j["end"] - j["start"]
        if a["start_hour"] + dur > 24:
            raise _Rule("the job lasts %d hours and would run past midnight" % dur)
        if j["date"] == a["date"] and j["start"] == a["start_hour"]:
            raise _Rule("job %s is already at that date and hour" % a["job_id"])
        j["date"], j["start"], j["end"] = a["date"], a["start_hour"], a["start_hour"] + dur
        return {"ok": True, "job": self._jview(a["job_id"])}

    def _t_cancel_job(self, a):
        j = self._job(a["job_id"])
        if j["status"] not in ("assigned", "unassigned"):
            raise _Rule("job %s is %s" % (a["job_id"], j["status"]))
        j["status"], j["vehicle"], j["driver"] = "cancelled", None, None
        return {"ok": True, "job": self._jview(a["job_id"])}

    def _t_schedule_maintenance(self, a):
        vid = a["vehicle_id"]
        self._veh(vid)
        self._future(a["date"])
        s, e = a["start_hour"], a["start_hour"] + a["duration_hours"]
        if e > 24:
            raise _Rule("the window would run past midnight")
        for k in self._jobs_of("vehicle", vid, a["date"]):
            o = self.state["jobs"][k]
            if o["start"] < e and s < o["end"]:
                raise _Rule("vehicle %s has job %s (%02d-%02d) in that window" % (vid, k, o["start"], o["end"]))
        for m, x in sorted(self.state["maintenance"].items()):
            if x["vehicle"] == vid and x["date"] == a["date"] and x["start"] < e and s < x["end"]:
                raise _Rule("vehicle %s already has maintenance %s (%02d-%02d) in that window" % (vid, m, x["start"], x["end"]))
        mid = "M-%d" % self.state["next_maint"]
        self.state["next_maint"] += 1
        self.state["maintenance"][mid] = {"vehicle": vid, "date": a["date"], "start": s, "end": e, "kind": a["kind"]}
        return {"ok": True, "maintenance_id": mid, "vehicle_id": vid, "date": a["date"], "start_hour": s, "end_hour": e}

    def _t_set_vehicle_status(self, a):
        vid = a["vehicle_id"]
        v = self._veh(vid)
        if v["status"] == a["status"]:
            raise _Rule("vehicle %s is already %s" % (vid, a["status"]))
        if a["status"] == "out_of_service":
            left = [k for k in self._jobs_of("vehicle", vid) if self.state["jobs"][k]["date"] >= self.state["today"]]
            if left:
                raise _Rule("vehicle %s still has assigned jobs from today onwards: %s" % (vid, ", ".join(left)))
        v["status"] = a["status"]
        return {"ok": True, "vehicle_id": vid, "status": v["status"]}


# --------------------------------------------------------------------------
# 5. hotel: rooms, guests, reservations, rate rules, payments
# --------------------------------------------------------------------------
_FEATURES = ["sea_view", "balcony", "accessible"]
_EXTRAS = ["breakfast", "parking"]
_ACTIVE = ("booked", "checked_in")


def _h_nights(ci, co):
    d, end, out = _pdate(ci), _pdate(co), []
    while d < end:
        out.append(d)
        d += datetime.timedelta(days=1)
    return out


def _h_room_part(st, rate_type, ci, co, tier, first_only=False):
    nights = _h_nights(ci, co)
    if first_only:
        nights = nights[:1]
    base = st["room_types"][rate_type]["rate"]
    raw = sum(base + (st["policy"]["weekend_surcharge"] if d.weekday() in (4, 5) else 0) for d in nights)
    return raw * (100 - st["policy"]["discount_pct"][tier]) // 100


def _h_total(st, r):
    tier = st["guests"][r["guest"]]["tier"]
    n = len(_h_nights(r["check_in"], r["check_out"]))
    return _h_room_part(st, r["rate_type"], r["check_in"], r["check_out"], tier) + \
        sum(st["policy"]["extras"][x] for x in r["extras"]) * n


class HotelEnv(_Env):
    TOOLS = [
        _fn("get_hotel_info", "Today's date and weekday, room types with nightly rates and maximum occupancy, and the "
            "hotel policy (pricing, discounts, cancellation fees, payment and check-out rules)."),
        _fn("find_guests", "Search guest profiles by name and/or loyalty tier.",
            {"query": _s("Case-insensitive text that must appear in the guest name."),
             "tier": _s("Only guests of this loyalty tier.", ["none", "gold", "platinum"])}),
        _fn("list_rooms", "Rooms with type, floor, features and status.",
            {"room_type": _s("Only rooms of this type.", ["standard", "deluxe", "family", "suite"]),
             "floor": _i("Only rooms on this floor.", 1, 4)}),
        _fn("search_availability", "Rooms that are in service and have no active reservation overlapping the given stay "
            "(the check-out day itself is free for a new arrival).",
            {"check_in": _s("First night, YYYY-MM-DD."), "check_out": _s("Departure date, YYYY-MM-DD."),
             "room_type": _s("Only rooms of this type.", ["standard", "deluxe", "family", "suite"]),
             "feature": _s("Only rooms with this feature.", _FEATURES)}, ["check_in", "check_out"]),
        _fn("list_reservations", "Reservations ordered by check-in date, 8 per page. Filters are optional and combine "
            "with AND. Money fields are only in get_reservation.",
            {"guest_id": _s("Only reservations of this guest."), "room_id": _s("Only reservations in this room."),
             "date": _s("Only reservations whose stay covers this date, from the check-in day up to and including the check-out day."),
             "status": _s("Only reservations in this status.", ["booked", "checked_in", "checked_out", "cancelled"]),
             "page": _PAGE}),
        _fn("get_reservation", "One reservation in detail: guest and tier, room, dates, extras, the type whose rate is "
            "charged, total, amount paid, cancellation fee, balance due.",
            {"reservation_id": _s("Reservation id, e.g. R-701.")}, ["reservation_id"]),
        _fn("book_room", "Create a new reservation; the total is priced automatically.",
            {"guest_id": _s("Guest id."), "room_id": _s("Room number."), "check_in": _s("YYYY-MM-DD."),
             "check_out": _s("YYYY-MM-DD."), "guests": _i("Number of people.", 1)},
            ["guest_id", "room_id", "check_in", "check_out", "guests"]),
        _fn("modify_reservation", "Change the room, dates and/or number of people of a booked or checked-in "
            "reservation; give only the fields that change. The total is re-priced automatically.",
            {"reservation_id": _s("Reservation id."), "room_id": _s("New room number."),
             "check_in": _s("New check-in date, YYYY-MM-DD."), "check_out": _s("New check-out date, YYYY-MM-DD."),
             "guests": _i("New number of people.", 1),
             "keep_rate": _b("Only meaningful together with room_id: true keeps charging the rate of the room type "
                             "that is charged now; otherwise the new room's type is charged.")},
            ["reservation_id"]),
        _fn("cancel_reservation", "Cancel a booked reservation. The cancellation fee is set according to policy.",
            {"reservation_id": _s("Reservation id.")}, ["reservation_id"]),
        _fn("set_extra", "Switch an extra on or off for a reservation (charged per night for the whole stay).",
            {"reservation_id": _s("Reservation id."), "extra": _s("Which extra.", _EXTRAS),
             "enabled": _b("true = add, false = remove.")}, ["reservation_id", "extra", "enabled"]),
        _fn("record_payment", "Charge the guest's card on file for an amount towards a reservation.",
            {"reservation_id": _s("Reservation id."), "amount": _i("Amount.", 1)}, ["reservation_id", "amount"]),
        _fn("refund", "Refund part of what was paid on a reservation.",
            {"reservation_id": _s("Reservation id."), "amount": _i("Amount.", 1)}, ["reservation_id", "amount"]),
        _fn("check_out", "Check a guest out.", {"reservation_id": _s("Reservation id.")}, ["reservation_id"]),
        _fn("set_room_status", "Put a room into maintenance or back in service.",
            {"room_id": _s("Room number."), "status": _s("New status.", ["ok", "maintenance"])}, ["room_id", "status"]),
    ]

    def _res(self, rid):
        r = self.state["reservations"].get(rid)
        if r is None:
            raise _Rule("unknown reservation '%s'" % rid[:30])
        return r

    def _room(self, k):
        r = self.state["rooms"].get(k)
        if r is None:
            raise _Rule("unknown room '%s'" % k[:30])
        return r

    def _owed(self, r):
        return r["fee"] if r["status"] == "cancelled" else r["total"]

    def _blocker(self, room, ci, co, skip=None):
        for k, r in sorted(self.state["reservations"].items()):
            if k != skip and r["room"] == room and r["status"] in _ACTIVE and r["check_in"] < co and ci < r["check_out"]:
                return k
        return None

    def _range(self, ci, co):
        a, b = _pdate(ci, "check_in"), _pdate(co, "check_out")
        if b <= a:
            raise _Rule("check_out must be after check_in")
        if (b - a).days > 30:
            raise _Rule("stays are limited to 30 nights")

    def _view(self, k, money=False):
        r = self.state["reservations"][k]
        g = self.state["guests"][r["guest"]]
        out = {"reservation_id": k, "guest_id": r["guest"], "guest_name": g["name"], "room_id": r["room"],
               "room_type": self.state["rooms"][r["room"]]["type"], "check_in": r["check_in"],
               "check_out": r["check_out"], "status": r["status"]}
        if money:
            out.update({"guest_tier": g["tier"], "guests": r["guests"], "extras": list(r["extras"]),
                        "rate_charged_for_type": r["rate_type"], "nights": len(_h_nights(r["check_in"], r["check_out"])),
                        "total": r["total"], "paid": r["paid"], "cancellation_fee": r["fee"],
                        "balance_due": self._owed(r) - r["paid"]})
        return out

    def _t_get_hotel_info(self, a):
        st = self.state
        p = st["policy"]
        return {"today": st["today"], "weekday": _DAYNAMES[_pdate(st["today"]).weekday()],
                "room_types": [{"room_type": k, "nightly_rate": v["rate"], "max_guests": v["max_guests"]}
                               for k, v in sorted(st["room_types"].items())],
                "policy": {
                    "weekend_surcharge_per_night": p["weekend_surcharge"],
                    "loyalty_discount_percent": dict(p["discount_pct"]),
                    "extras_per_night": dict(p["extras"]),
                    "free_cancellation_days": p["free_cancel_days"],
                    "rules": [
                        "Room charge = nightly rate of the charged room type for every night of the stay, plus the weekend "
                        "surcharge for Friday and Saturday nights, minus the guest's loyalty discount. Extras are added "
                        "per night and are not discounted.",
                        "Cancellation: free if cancelled at least free_cancellation_days days before the check-in date. "
                        "Later than that (including no-shows) the fee is the discounted room charge of the first night.",
                        "A refund may not exceed what was paid minus what is owed (the total for active or completed "
                        "stays, the cancellation fee for cancelled ones). A payment may not exceed the balance due.",
                        "A guest can be checked out only on their check-out date and only when the balance due is exactly 0.",
                        "A room cannot be put into maintenance while a guest is staying in it or a booked reservation "
                        "for it has not started yet; move those reservations first.",
                        "A room can be changed for a checked-in guest; the new room must be free from today until check-out.",
                    ]}}

    def _t_find_guests(self, a):
        q = a.get("query", "").strip().lower()
        out = [{"guest_id": k, "name": g["name"], "tier": g["tier"]} for k, g in sorted(self.state["guests"].items())
               if q in g["name"].lower() and ("tier" not in a or g["tier"] == a["tier"])]
        return {"guests": out}

    def _rview(self, k):
        r = self.state["rooms"][k]
        return {"room_id": k, "room_type": r["type"], "floor": r["floor"], "features": list(r["features"]), "status": r["status"]}

    def _t_list_rooms(self, a):
        return {"rooms": [self._rview(k) for k, r in sorted(self.state["rooms"].items())
                          if ("room_type" not in a or r["type"] == a["room_type"]) and ("floor" not in a or r["floor"] == a["floor"])]}

    def _t_search_availability(self, a):
        self._range(a["check_in"], a["check_out"])
        out = []
        for k, r in sorted(self.state["rooms"].items()):
            if r["status"] != "ok" or ("room_type" in a and r["type"] != a["room_type"]) or \
                    ("feature" in a and a["feature"] not in r["features"]):
                continue
            if self._blocker(k, a["check_in"], a["check_out"]) is None:
                out.append(self._rview(k))
        return {"check_in": a["check_in"], "check_out": a["check_out"], "available_rooms": out}

    def _t_list_reservations(self, a):
        if "guest_id" in a and a["guest_id"] not in self.state["guests"]:
            raise _Rule("unknown guest '%s'" % a["guest_id"][:30])
        if "room_id" in a:
            self._room(a["room_id"])
        if "date" in a:
            _pdate(a["date"])
        rows = []
        for k, r in self.state["reservations"].items():
            if ("guest_id" in a and r["guest"] != a["guest_id"]) or ("room_id" in a and r["room"] != a["room_id"]) or \
                    ("status" in a and r["status"] != a["status"]) or \
                    ("date" in a and not (r["check_in"] <= a["date"] <= r["check_out"])):
                continue
            rows.append((r["check_in"], k))
        rows.sort()
        meta, rows = _paged(rows, a.get("page", 1), 8)
        meta["reservations"] = [self._view(k) for _, k in rows]
        return meta

    def _t_get_reservation(self, a):
        self._res(a["reservation_id"])
        return self._view(a["reservation_id"], True)

    def _fits(self, room_id, guests):
        mx = self.state["room_types"][self.state["rooms"][room_id]["type"]]["max_guests"]
        if guests > mx:
            raise _Rule("room %s (%s) sleeps at most %d" % (room_id, self.state["rooms"][room_id]["type"], mx))

    def _t_book_room(self, a):
        st = self.state
        if a["guest_id"] not in st["guests"]:
            raise _Rule("unknown guest '%s'" % a["guest_id"][:30])
        room = self._room(a["room_id"])
        self._range(a["check_in"], a["check_out"])
        if a["check_in"] < st["today"]:
            raise _Rule("check_in is in the past")
        if room["status"] != "ok":
            raise _Rule("room %s is in maintenance" % a["room_id"])
        self._fits(a["room_id"], a["guests"])
        b = self._blocker(a["room_id"], a["check_in"], a["check_out"])
        if b:
            raise _Rule("room %s is not free for those dates (reservation %s)" % (a["room_id"], b))
        rid = "R-%d" % st["next_res"]
        st["next_res"] += 1
        r = {"guest": a["guest_id"], "room": a["room_id"], "rate_type": room["type"], "check_in": a["check_in"],
             "check_out": a["check_out"], "guests": a["guests"], "status": "booked", "extras": [], "total": 0,
             "paid": 0, "fee": 0}
        r["total"] = _h_total(st, r)
        st["reservations"][rid] = r
        return {"ok": True, "reservation": self._view(rid, True)}

    def _t_modify_reservation(self, a):
        st = self.state
        rid = a["reservation_id"]
        r = self._res(rid)
        if r["status"] not in _ACTIVE:
            raise _Rule("reservation %s is %s and cannot be modified" % (rid, r["status"]))
        if not [k for k in ("room_id", "check_in", "check_out", "guests") if k in a]:
            raise _Rule("nothing to change: give room_id, check_in, check_out and/or guests")
        room = a.get("room_id", r["room"])
        ci, co = a.get("check_in", r["check_in"]), a.get("check_out", r["check_out"])
        guests = a.get("guests", r["guests"])
        self._room(room)
        self._range(ci, co)
        if r["status"] == "checked_in":
            if ci != r["check_in"]:
                raise _Rule("the guest has already checked in; the check-in date cannot change")
            if co < st["today"]:
                raise _Rule("check_out cannot be before today")
        elif ci < st["today"]:
            raise _Rule("check_in cannot be moved into the past (today is %s)" % st["today"])
        if room != r["room"] and st["rooms"][room]["status"] != "ok":
            raise _Rule("room %s is in maintenance" % room)
        self._fits(room, guests)
        frm = max(ci, st["today"]) if r["status"] == "checked_in" else ci
        b = self._blocker(room, frm, co, skip=rid)
        if b:
            o = st["reservations"][b]
            raise _Rule("room %s is not free for %s to %s: reservation %s (%s to %s)" % (
                room, frm, co, b, o["check_in"], o["check_out"]))
        if room != r["room"] and not a.get("keep_rate", False):
            r["rate_type"] = st["rooms"][room]["type"]
        r["room"], r["check_in"], r["check_out"], r["guests"] = room, ci, co, guests
        r["total"] = _h_total(st, r)
        return {"ok": True, "reservation": self._view(rid, True)}

    def _t_cancel_reservation(self, a):
        st = self.state
        rid = a["reservation_id"]
        r = self._res(rid)
        if r["status"] != "booked":
            raise _Rule("only booked reservations can be cancelled; %s is %s" % (rid, r["status"]))
        days = (_pdate(r["check_in"]) - _pdate(st["today"])).days
        if days >= st["policy"]["free_cancel_days"]:
            r["fee"] = 0
        else:
            r["fee"] = _h_room_part(st, r["rate_type"], r["check_in"], r["check_out"], st["guests"][r["guest"]]["tier"], True)
        r["status"] = "cancelled"
        return {"ok": True, "reservation": self._view(rid, True)}

    def _t_set_extra(self, a):
        rid = a["reservation_id"]
        r = self._res(rid)
        if r["status"] not in _ACTIVE:
            raise _Rule("reservation %s is %s and cannot be modified" % (rid, r["status"]))
        if a["enabled"] == (a["extra"] in r["extras"]):
            raise _Rule("%s is already %s on %s" % (a["extra"], "on" if a["enabled"] else "off", rid))
        if a["enabled"]:
            r["extras"] = sorted(r["extras"] + [a["extra"]])
        else:
            r["extras"].remove(a["extra"])
        r["total"] = _h_total(self.state, r)
        return {"ok": True, "reservation": self._view(rid, True)}

    def _t_record_payment(self, a):
        rid = a["reservation_id"]
        r = self._res(rid)
        due = self._owed(r) - r["paid"]
        if a["amount"] > due:
            raise _Rule("payment %d exceeds the balance due on %s (%d)" % (a["amount"], rid, max(due, 0)))
        r["paid"] += a["amount"]
        return {"ok": True, "reservation_id": rid, "paid": r["paid"], "balance_due": self._owed(r) - r["paid"]}

    def _t_refund(self, a):
        rid = a["reservation_id"]
        r = self._res(rid)
        over = r["paid"] - self._owed(r)
        if a["amount"] > over:
            raise _Rule("refund %d exceeds what can be refunded on %s (paid %d, owed %d, refundable %d)" % (
                a["amount"], rid, r["paid"], self._owed(r), max(over, 0)))
        r["paid"] -= a["amount"]
        return {"ok": True, "reservation_id": rid, "paid": r["paid"], "balance_due": self._owed(r) - r["paid"]}

    def _t_check_out(self, a):
        rid = a["reservation_id"]
        r = self._res(rid)
        if r["status"] != "checked_in":
            raise _Rule("reservation %s is %s, not checked_in" % (rid, r["status"]))
        if r["check_out"] != self.state["today"]:
            raise _Rule("reservation %s is due to check out on %s, not today" % (rid, r["check_out"]))
        if r["paid"] != r["total"]:
            raise _Rule("balance due on %s is %d; it must be exactly 0 before check-out" % (rid, r["total"] - r["paid"]))
        r["status"] = "checked_out"
        return {"ok": True, "reservation_id": rid, "status": "checked_out"}

    def _t_set_room_status(self, a):
        k = a["room_id"]
        room = self._room(k)
        if room["status"] == a["status"]:
            raise _Rule("room %s already has status %s" % (k, a["status"]))
        if a["status"] == "maintenance":
            blk = [x for x, r in sorted(self.state["reservations"].items())
                   if r["room"] == k and r["status"] in _ACTIVE and r["check_out"] > self.state["today"]]
            if blk:
                raise _Rule("room %s still has active reservations: %s" % (k, ", ".join(blk)))
        room["status"] = a["status"]
        return {"ok": True, "room_id": k, "status": a["status"]}


ENVS = {"bank": BankEnv, "deploy": DeployEnv, "registrar": RegistrarEnv, "fleet": FleetEnv, "hotel": HotelEnv}


# --------------------------------------------------------------------------
# check helpers
# --------------------------------------------------------------------------
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


def _is_collection(v):
    return isinstance(v, dict) and len(v) > 0 and all(isinstance(x, dict) for x in v.values())


def _final(s, i, changes=None, new=None):
    """True iff state s equals init i except for exactly the described differences.

    changes: {collection: {record_id: {field: value | predicate}}}; for non-collection top-level keys
             {key: value | predicate}.
    new:     {collection: [ {field: value | predicate}, ... ]} records that must have been created
             (matched by content, generated ids ignored). Collections not listed must have no new records.
    Counters (next_*) and the free-form activity "log" are ignored. Every record and field not mentioned
    must be identical to init.
    """
    changes = changes or {}
    new = new or {}
    if not isinstance(s, dict) or set(s.keys()) != set(i.keys()):
        return False
    for key in i:
        if key.startswith("next_") or key == "log":
            continue
        if _is_collection(i[key]):
            if not isinstance(s[key], dict):
                return False
            for rid, rec in i[key].items():
                got = s[key].get(rid)
                if not isinstance(got, dict) or set(got.keys()) != set(rec.keys()):
                    return False
                ch = changes.get(key, {}).get(rid, {})
                for f in rec:
                    want = ch[f] if f in ch else rec[f]
                    if callable(want):
                        if not want(got[f]):
                            return False
                    elif got[f] != want:
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


def _set(xs):
    xs = sorted(xs)
    return lambda v: isinstance(v, list) and sorted(v) == xs


def _mg(d, upd):
    out = copy.deepcopy(d)
    out.update(upd)
    return out


TASKS = []


def _add(tid, env, init, prompt, reference, trap, check, ref_errors=(), mentions=(), creates=(), seq=()):
    """mentions: strings the prompt names that must exist in init (checked mechanically, with the ids/quoted
    names the verifier extracts itself). creates: prompt strings that are to be created, exempt from that check.
    seq: groups of reference indices whose relative order is part of the task (not permuted by the order test)."""
    frozen = copy.deepcopy(init)
    TASKS.append({
        "id": tid, "env": env, "init": init, "prompt": prompt,
        "reference": reference, "ref_errors": list(ref_errors), "trap": trap,
        "mentions": list(mentions), "creates": list(creates), "seq": [list(g) for g in seq],
        "check": (lambda state, _c=check, _i=frozen: bool(_c(state, _i))),
    })


# --------------------------------------------------------------------------
# bank fixture + tasks T01-T06
# --------------------------------------------------------------------------
def _bank():
    def acct(owner, typ, nick, bal, status="open"):
        return {"owner": owner, "type": typ, "nickname": nick, "balance": bal, "status": status}

    def hold(account, amount, reason, placed, expires, status="active"):
        return {"account": account, "amount": amount, "reason": reason, "placed": placed, "expires": expires,
                "status": status}

    def sched(frm, payee, amount, date, status="pending"):
        return {"from": frm, "payee": payee, "amount": amount, "date": date, "status": status}

    tx = {}

    def add_tx(account, rows):
        for xid, date, typ, amount, desc in rows:
            rev = desc.endswith("*")
            tx["X-%d" % xid] = {"account": account, "date": "2026-" + date, "type": typ, "amount": amount,
                                "description": desc.rstrip("*"), "reversed": rev}

    od, mo, atm = "Overdraft fee", "Monthly account fee", "ATM withdrawal fee"
    add_tx("A-2020", [
        (5101, "06-28", "fee", -25, od), (5102, "07-01", "deposit", 2100, "Salary Nordlicht GmbH"),
        (5104, "07-06", "fee", -25, od), (5106, "07-19", "card", -84, "Markt Frisch"),
        (5108, "07-31", "fee", -6, mo), (5110, "08-01", "deposit", 2100, "Salary Nordlicht GmbH"),
        (5112, "08-14", "fee", -25, od), (5115, "08-14", "fee", -3, atm),
        (5117, "08-20", "card", -310, "Zahnarzt Dr. Kemal"), (5119, "08-29", "fee", -25, od + "*"),
        (5121, "08-31", "fee", -6, mo), (5123, "09-01", "deposit", 2100, "Salary Nordlicht GmbH"),
        (5126, "09-09", "fee", -25, od), (5128, "09-15", "card", -145, "Bahn Ticket"),
        (5130, "09-22", "fee", -30, od), (5133, "09-30", "fee", -6, mo),
        (5135, "10-01", "deposit", 2100, "Salary Nordlicht GmbH"), (5137, "10-02", "fee", -30, od),
        (5139, "10-05", "card", -62, "Tanke Elbe")])
    add_tx("A-2021", [(5140, "09-15", "fee", -25, od), (5141, "09-20", "card", -40, "Markt Frisch")])
    add_tx("A-2023", [(5150, "09-12", "fee", -25, od)])
    add_tx("A-2050", [
        (5201, "09-10", "card", -9, "Baeckerei Thoms"), (5202, "09-12", "card", -64, "Fuelpoint Nord"),
        (5203, "09-12", "card", -64, "Fuelpoint Nord"), (5204, "09-14", "card", -13, "Streamly"),
        (5205, "09-15", "deposit", 2900, "Salary Hafenklinik"), (5206, "09-17", "card", -48, "Markt Frisch"),
        (5207, "09-17", "card", -84, "Markt Frisch"), (5208, "09-19", "card", -120, "Rad & Tat"),
        (5209, "09-19", "card", -120, "Rad & Tat*"), (5210, "09-21", "card", -64, "Fuelpoint Nord"),
        (5211, "09-23", "card", -310, "Hotel Seeblick"), (5212, "09-23", "card", -310, "Hotel Seeblick"),
        (5213, "09-24", "card", -9, "Baeckerei Thoms"), (5214, "09-25", "card", -9, "Baeckerei Thoms"),
        (5215, "09-26", "fee", -6, mo), (5216, "09-28", "card", -27, "Apotheke am Ring"),
        (5217, "09-28", "card", -27, "Apotheke am Ring"), (5218, "09-28", "card", -27, "Apotheke am Ring"),
        (5219, "09-30", "card", -48, "Markt Frisch"), (5220, "10-01", "card", -13, "Streamly"),
        (5221, "10-02", "card", -35, "Buchhandlung Lenz"), (5222, "10-02", "card", -35, "Markt Frisch"),
        (5223, "10-05", "card", -58, "Tanke Elbe"), (5224, "10-05", "card", -58, "Tanke Elbe"),
        (5225, "10-06", "card", -22, "Kino Passage")])
    add_tx("A-2060", [
        (5301, "08-28", "deposit", 4650, "Salary Kettler AG"), (5303, "09-02", "card", -120, "Baumarkt Holz & Co"),
        (5305, "09-10", "card", -75, "Tanke Elbe"), (5307, "09-18", "transfer_out", -500, "To House deposit"),
        (5310, "09-29", "deposit", 4700, "Salary Kettler AG"), (5311, "09-30", "fee", -6, mo),
        (5312, "10-01", "deposit", 380, "Tax refund Finanzamt"), (5314, "10-05", "deposit", 120, "Cash deposit"),
        (5315, "10-06", "card", -48, "Markt Frisch")])
    add_tx("A-2070", [
        (5399, "08-29", "deposit", 2000, "Invoice 109 Atelier Kranz"),
        (5401, "09-03", "deposit", 1800, "Invoice 114 Morgenrot Verlag"), (5402, "09-05", "card", -260, "Papierhaus"),
        (5404, "09-11", "deposit", 2460, "Invoice 115 Hafen Cafe"), (5405, "09-12", "transfer_in", 700, "From Rainy day"),
        (5406, "09-14", "fee", -12, mo), (5407, "09-18", "deposit", 940, "Invoice 116 Studio Lumen"),
        (5408, "09-20", "card", -130, "Druckerei Voss"), (5410, "09-27", "deposit", 3200, "Invoice 117 Morgenrot Verlag"),
        (5411, "09-30", "transfer_out", -1500, "To Tax reserve"), (5413, "10-02", "deposit", 1500, "Invoice 118 Hafen Cafe"),
        (5414, "10-06", "card", -89, "Software Abo")])
    return {
        "today": "2026-10-08",
        "policy": {"max_single_transfer": 5000, "fee_reversal_days": 90, "card_reversal_days": 30, "schedule_max_days": 90},
        "customers": {
            "C-101": {"name": "Marta Lindqvist", "segment": "personal"},
            "C-102": {"name": "Marta Lindgren", "segment": "personal"},
            "C-103": {"name": "Halden Print Works", "segment": "business"},
            "C-104": {"name": "Ilse Brandt", "segment": "personal"},
            "C-105": {"name": "Tomas Okafor", "segment": "personal"},
            "C-106": {"name": "Dario Ferrand", "segment": "personal"},
            "C-107": {"name": "Lucia Ferrand", "segment": "personal"},
            "C-108": {"name": "Lucia Ferrant", "segment": "personal"},
            "C-109": {"name": "Noor Haddad", "segment": "personal"},
            "C-110": {"name": "Bruno Keller", "segment": "personal"},
            "C-111": {"name": "Sable & Finch Studio", "segment": "business"},
            "C-112": {"name": "Ilsa Brandt", "segment": "personal"},
        },
        "payees": {"P-01": "Halden Energy", "P-02": "Nordwind Travel", "P-03": "Brueckner Immobilien",
                   "P-04": "Kite Insurance", "P-05": "Alpenhof Lodge", "P-06": "Stadtwerke Water",
                   "P-07": "Autohaus Renner Leasing", "P-08": "Kettler Pension Plan"},
        "accounts": {
            "A-2001": acct("C-101", "checking", "Everyday", 1420),
            "A-2002": acct("C-101", "savings", "Holiday fund", 7360),
            "A-2003": acct("C-101", "savings", "Holiday fund 2027", 950),
            "A-2004": acct("C-102", "checking", "Everyday", 600),
            "A-2005": acct("C-102", "savings", "Holiday fund", 2100),
            "A-2010": acct("C-103", "checking", "Operating", 9850),
            "A-2011": acct("C-103", "checking", "Payroll", 3400),
            "A-2012": acct("C-103", "checking", "Card settlements", 1980),
            "A-2013": acct("C-103", "checking", "Petty cash", 1000),
            "A-2014": acct("C-103", "checking", "Old operating", 0, "closed"),
            "A-2015": acct("C-103", "savings", "Tax savings", 6200),
            "A-2016": acct("C-103", "reserve", "Reserve", 12000),
            "A-2017": acct("C-103", "checking", "Suppliers", 2750),
            "A-2018": acct("C-103", "checking", "Online shop", 4300),
            "A-2020": acct("C-104", "checking", "Everyday", 60),
            "A-2021": acct("C-104", "checking", "Joint household", 800),
            "A-2022": acct("C-104", "savings", "Rainy day", 2300),
            "A-2023": acct("C-112", "checking", "Everyday", 400),
            "A-2030": acct("C-105", "checking", "Main", 1840),
            "A-2031": acct("C-105", "savings", "Buffer", 2000),
            "A-2032": acct("C-105", "checking", "Side gigs", 700),
            "A-2040": acct("C-106", "checking", "Current", 5900),
            "A-2041": acct("C-106", "savings", "Savings", 4000),
            "A-2042": acct("C-107", "checking", "Current", 1200),
            "A-2043": acct("C-107", "savings", "Savings", 3000),
            "A-2044": acct("C-108", "checking", "Current", 300),
            "A-2050": acct("C-109", "checking", "Main", 2240),
            "A-2051": acct("C-109", "savings", "Nest", 5000),
            "A-2060": acct("C-110", "checking", "Salary account", 3100),
            "A-2061": acct("C-110", "savings", "House deposit", 15200),
            "A-2062": acct("C-110", "reserve", "Emergency pot", 2450),
            "A-2070": acct("C-111", "checking", "Operating", 6400),
            "A-2071": acct("C-111", "reserve", "Tax reserve", 1900),
            "A-2072": acct("C-111", "savings", "Rainy day", 800),
        },
        "holds": {
            "H-300": hold("A-2002", 150, "pending_card", "2026-08-02", "2026-08-09", "released"),
            "H-301": hold("A-2002", 400, "deposit_check", "2026-09-25", "2026-10-02"),
            "H-302": hold("A-2002", 85, "pending_card", "2026-09-29", "2026-10-06"),
            "H-303": hold("A-2003", 60, "pending_card", "2026-10-05", "2026-10-12"),
            "H-310": hold("A-2010", 1250, "pending_card", "2026-10-03", "2026-10-10"),
            "H-311": hold("A-2012", 1100, "dispute", "2026-09-30", "2026-10-30"),
            "H-312": hold("A-2017", 500, "earmark", "2026-08-15", "2026-09-15", "released"),
            "H-313": hold("A-2017", 300, "pending_card", "2026-10-02", "2026-10-09"),
            "H-320": hold("A-2030", 300, "pending_card", "2026-10-04", "2026-10-11"),
            "H-321": hold("A-2031", 900, "earmark", "2026-09-01", "2026-12-01"),
            "H-330": hold("A-2040", 450, "pending_card", "2026-09-28", "2026-10-05"),
            "H-331": hold("A-2040", 600, "pending_card", "2026-10-05", "2026-10-12"),
            "H-332": hold("A-2040", 250, "dispute", "2026-09-01", "2026-10-01"),
            "H-333": hold("A-2040", 500, "deposit_check", "2026-09-10", "2026-09-17", "released"),
            "H-340": hold("A-2071", 1500, "earmark", "2026-07-01", "2026-09-30"),
            "H-341": hold("A-2071", 800, "earmark", "2026-04-01", "2026-06-30", "released"),
        },
        "transactions": tx,
        "scheduled": {
            "S-401": sched("A-2002", "P-02", 300, "2026-10-20"),
            "S-402": sched("A-2002", "P-05", 450, "2026-11-03"),
            "S-403": sched("A-2002", "P-02", 300, "2026-09-20", "executed"),
            "S-404": sched("A-2003", "P-02", 120, "2026-10-25"),
            "S-410": sched("A-2030", "P-01", 210, "2026-10-09"),
            "S-411": sched("A-2030", "P-03", 650, "2026-10-12"),
            "S-412": sched("A-2030", "P-04", 730, "2026-10-13"),
            "S-413": sched("A-2030", "P-06", 120, "2026-10-15"),
            "S-414": sched("A-2030", "P-07", 900, "2026-10-14"),
            "S-415": sched("A-2030", "P-02", 250, "2026-10-16"),
            "S-416": sched("A-2030", "P-01", 400, "2026-10-10", "cancelled"),
            "S-417": sched("A-2032", "P-04", 95, "2026-10-12"),
            "S-418": sched("A-2030", "P-06", 115, "2026-09-15", "executed"),
            "S-430": sched("A-2060", "P-08", 200, "2026-10-28"),
            "S-431": sched("A-2060", "P-01", 95, "2026-10-15"),
            "S-432": sched("A-2060", "P-08", 200, "2026-09-28", "executed"),
        },
        "log": [],
        "next_hold": 350,
        "next_sched": 440,
    }


def _bal(i, upd):
    """accounts changes: {account_id: delta} -> {account_id: {"balance": new}}"""
    return dict((k, {"balance": i["accounts"][k]["balance"] + d}) for k, d in upd.items())


_add("T01", "bank", _bank(),
     "Marta Lindqvist wants to close her 'Holiday fund' savings account (the one called exactly that, not her "
     "'Holiday fund 2027'). Everything in it should end up in her 'Everyday' checking account. The payments that are "
     "still scheduled to go out of the Holiday fund must keep running: set each of them up again from the Everyday "
     "account with the same payee, amount and date. Sort out whatever stands in the way of closing the account, "
     "then close it. Careful, there is another customer called Marta with similarly named accounts; her accounts "
     "and Marta Lindqvist's other accounts must not change.",
     [["find_customers", {"query": "Marta"}], ["list_accounts", {"customer_id": "C-101"}],
      ["get_account", {"account_id": "A-2002"}], ["list_holds", {"account_id": "A-2002", "status": "active"}],
      ["list_scheduled", {"account_id": "A-2002", "status": "pending"}],
      ["release_hold", {"hold_id": "H-301"}], ["release_hold", {"hold_id": "H-302"}],
      ["cancel_scheduled", {"scheduled_id": "S-401"}], ["cancel_scheduled", {"scheduled_id": "S-402"}],
      ["schedule_payment", {"from_account": "A-2001", "payee_id": "P-02", "amount": 300, "date": "2026-10-20"}],
      ["schedule_payment", {"from_account": "A-2001", "payee_id": "P-05", "amount": 450, "date": "2026-11-03"}],
      ["transfer", {"from_account": "A-2002", "to_account": "A-2001", "amount": 5000}],
      ["transfer", {"from_account": "A-2002", "to_account": "A-2001", "amount": 2360}],
      ["close_account", {"account_id": "A-2002"}]],
     [["release_hold", {"hold_id": "H-301"}], ["release_hold", {"hold_id": "H-302"}],
      ["cancel_scheduled", {"scheduled_id": "S-401"}], ["cancel_scheduled", {"scheduled_id": "S-402"}],
      ["transfer", {"from_account": "A-2002", "to_account": "A-2001", "amount": 5000}],
      ["transfer", {"from_account": "A-2002", "to_account": "A-2001", "amount": 2360}],
      ["close_account", {"account_id": "A-2002"}]],
     lambda s, i: _final(s, i, changes={
         "accounts": {"A-2001": {"balance": 8780}, "A-2002": {"balance": 0, "status": "closed"}},
         "holds": {"H-301": {"status": "released"}, "H-302": {"status": "released"}},
         "scheduled": {"S-401": {"status": "cancelled"}, "S-402": {"status": "cancelled"}}},
         new={"scheduled": [
             {"from": "A-2001", "payee": "P-02", "amount": 300, "date": "2026-10-20", "status": "pending"},
             {"from": "A-2001", "payee": "P-05", "amount": 450, "date": "2026-11-03", "status": "pending"}]}),
     mentions=["Marta Lindqvist", "Holiday fund", "Holiday fund 2027", "Everyday"])


def _c02(s, i):
    exp = {}
    for k, a in i["accounts"].items():
        if a["owner"] == "C-103" and a["type"] == "checking" and a["status"] == "open":
            held = sum(h["amount"] for h in i["holds"].values() if h["account"] == k and h["status"] == "active")
            if a["balance"] - held > 1000:
                exp[k] = -(a["balance"] - held - 1000)
    exp["A-2016"] = -sum(exp.values())
    return sorted(exp) == ["A-2010", "A-2011", "A-2016", "A-2017", "A-2018"] and \
        _final(s, i, changes={"accounts": _bal(i, exp)})


_add("T02", "bank", _bank(),
     "Month-end sweep for Halden Print Works. Every open checking account of theirs should be left with exactly "
     "1,000 in available funds - available meaning the balance minus the holds that are currently active on that "
     "account - and whatever is above that goes into their 'Reserve' account. A checking account whose available "
     "funds are already at or below 1,000 is left alone. Their savings account is not part of the sweep. Do not "
     "release or place any holds, and respect the bank's transfer rules.",
     [["find_customers", {"query": "Halden"}], ["list_accounts", {"customer_id": "C-103"}], ["get_bank_info", {}],
      ["get_account", {"account_id": "A-2010"}], ["get_account", {"account_id": "A-2011"}],
      ["get_account", {"account_id": "A-2012"}], ["get_account", {"account_id": "A-2013"}],
      ["get_account", {"account_id": "A-2017"}], ["get_account", {"account_id": "A-2018"}],
      ["transfer", {"from_account": "A-2010", "to_account": "A-2016", "amount": 5000}],
      ["transfer", {"from_account": "A-2010", "to_account": "A-2016", "amount": 2600}],
      ["transfer", {"from_account": "A-2011", "to_account": "A-2016", "amount": 2400}],
      ["transfer", {"from_account": "A-2017", "to_account": "A-2016", "amount": 1450}],
      ["transfer", {"from_account": "A-2018", "to_account": "A-2016", "amount": 3300}]],
     [["transfer", {"from_account": "A-2010", "to_account": "A-2016", "amount": 5000}],
      ["transfer", {"from_account": "A-2010", "to_account": "A-2016", "amount": 2600}],
      ["transfer", {"from_account": "A-2011", "to_account": "A-2016", "amount": 2400}],
      ["transfer", {"from_account": "A-2017", "to_account": "A-2016", "amount": 950}],
      ["transfer", {"from_account": "A-2018", "to_account": "A-2016", "amount": 3300}]],
     _c02, mentions=["Halden Print Works", "Reserve"])


def _c03(s, i):
    q3 = [k for k, x in i["transactions"].items()
          if x["account"] == "A-2020" and x["type"] == "fee" and x["description"] == "Overdraft fee"
          and "2026-07-01" <= x["date"] <= "2026-09-30" and not x["reversed"]
          and (_pdate(i["today"]) - _pdate(x["date"])).days <= i["policy"]["fee_reversal_days"]]
    back = -sum(i["transactions"][k]["amount"] for k in q3)
    bal = i["accounts"]["A-2020"]["balance"] + back
    top = max(0, 150 - bal)
    return sorted(q3) == ["X-5112", "X-5126", "X-5130"] and top == 10 and _final(s, i, changes={
        "transactions": dict((k, {"reversed": True}) for k in q3),
        "accounts": _bal(i, {"A-2020": back + top, "A-2022": -top})})


_add("T03", "bank", _bank(),
     "Ilse Brandt (careful: not Ilsa Brandt) was promised a goodwill gesture. Reverse every overdraft fee that was "
     "charged to her 'Everyday' checking account during the third quarter of 2026 (1 July to 30 September) and has "
     "not been reversed already. If bank policy does not allow one of them to be reversed, skip that one. Other "
     "kinds of fee stay as they are, and so do fees on her other accounts. When that is done, look at the Everyday "
     "balance: if it is below 150, top it up to exactly 150 from her 'Rainy day' savings; if it is 150 or more, "
     "move nothing.",
     [["find_customers", {"query": "Brandt"}], ["list_accounts", {"customer_id": "C-104"}], ["get_bank_info", {}],
      ["list_transactions", {"account_id": "A-2020", "type": "fee"}],
      ["list_transactions", {"account_id": "A-2020", "type": "fee", "page": 2}],
      ["reverse_transaction", {"transaction_id": "X-5104"}],
      ["reverse_transaction", {"transaction_id": "X-5112"}], ["reverse_transaction", {"transaction_id": "X-5126"}],
      ["reverse_transaction", {"transaction_id": "X-5130"}], ["get_account", {"account_id": "A-2020"}],
      ["transfer", {"from_account": "A-2022", "to_account": "A-2020", "amount": 10}]],
     [["reverse_transaction", {"transaction_id": "X-5112"}], ["reverse_transaction", {"transaction_id": "X-5126"}],
      ["reverse_transaction", {"transaction_id": "X-5130"}], ["reverse_transaction", {"transaction_id": "X-5137"}]],
     _c03, ref_errors=[5], mentions=["Ilse Brandt", "Ilsa Brandt", "Everyday", "Rainy day"])

_add("T04", "bank", _bank(),
     "Tomas Okafor is worried about the payments scheduled to leave his 'Main' checking account from now up to and "
     "including 15 October 2026. Once all of those have gone out he wants at least 200 of today's available funds "
     "(balance minus active holds) still left in Main. If it falls short, move exactly the shortfall from his "
     "'Buffer' savings - but only if Buffer's own available funds cover the whole shortfall. If they don't, move "
     "nothing yet: first postpone the single largest payment in that window to 22 October 2026 (cancel it and "
     "schedule it again with the same payee and amount), then work out the shortfall again and move exactly that "
     "from Buffer. Leave his other payments, accounts and holds alone.",
     [["find_customers", {"query": "Okafor"}], ["list_accounts", {"customer_id": "C-105"}],
      ["get_account", {"account_id": "A-2030"}], ["list_scheduled", {"account_id": "A-2030"}],
      ["list_scheduled", {"account_id": "A-2030", "page": 2}], ["get_account", {"account_id": "A-2031"}],
      ["cancel_scheduled", {"scheduled_id": "S-414"}],
      ["schedule_payment", {"from_account": "A-2030", "payee_id": "P-07", "amount": 900, "date": "2026-10-22"}],
      ["transfer", {"from_account": "A-2031", "to_account": "A-2030", "amount": 370}]],
     [["transfer", {"from_account": "A-2031", "to_account": "A-2030", "amount": 970}]],
     lambda s, i: _final(s, i, changes={
         "accounts": _bal(i, {"A-2030": 370, "A-2031": -370}),
         "scheduled": {"S-414": {"status": "cancelled"}}},
         new={"scheduled": [{"from": "A-2030", "payee": "P-07", "amount": 900, "date": "2026-10-22",
                             "status": "pending"}]}),
     mentions=["Tomas Okafor", "Main", "Buffer"])

_add("T05", "bank", _bank(),
     "Dario Ferrand is lending his sister Lucia Ferrand 6,500. It has to arrive in her checking account and come "
     "out of his checking account. Use the money in his checking account as far as possible: first release every "
     "hold on his checking account that has passed its expiry date, as far as bank policy lets you release it. "
     "Holds that have not expired stay. Then, only if his available funds still fall short of 6,500, bring in "
     "exactly the missing amount from his savings account - not a cent more - and send the 6,500 to Lucia. Make "
     "sure it goes to the right Lucia; nothing else may change.",
     [["find_customers", {"query": "Ferrand"}], ["list_accounts", {"customer_id": "C-106"}],
      ["list_accounts", {"customer_id": "C-107"}], ["get_bank_info", {}],
      ["list_holds", {"account_id": "A-2040", "status": "active"}],
      ["release_hold", {"hold_id": "H-330"}], ["release_hold", {"hold_id": "H-332"}],
      ["get_account", {"account_id": "A-2040"}],
      ["transfer", {"from_account": "A-2041", "to_account": "A-2040", "amount": 1450}],
      ["transfer", {"from_account": "A-2040", "to_account": "A-2042", "amount": 5000}],
      ["transfer", {"from_account": "A-2040", "to_account": "A-2042", "amount": 1500}]],
     [["release_hold", {"hold_id": "H-330"}],
      ["transfer", {"from_account": "A-2041", "to_account": "A-2040", "amount": 1200}],
      ["transfer", {"from_account": "A-2040", "to_account": "A-2042", "amount": 5000}],
      ["transfer", {"from_account": "A-2040", "to_account": "A-2042", "amount": 1250}]],
     lambda s, i: _final(s, i, changes={
         "accounts": _bal(i, {"A-2040": 1450 - 6500, "A-2041": -1450, "A-2042": 6500}),
         "holds": {"H-330": {"status": "released"}}}),
     ref_errors=[6], mentions=["Dario Ferrand", "Lucia Ferrand"])


def _c06(s, i):
    seen, extra = {}, []
    for k in sorted(i["transactions"]):
        x = i["transactions"][k]
        if x["account"] != "A-2050" or x["type"] != "card" or x["date"] < "2026-09-08":
            continue
        key = (x["description"], x["amount"], x["date"])
        if key in seen and not x["reversed"]:
            extra.append(k)
        seen[key] = True
    back = -sum(i["transactions"][k]["amount"] for k in extra)
    move = max(0, i["accounts"]["A-2050"]["balance"] + back - 2500)
    return extra == ["X-5203", "X-5212", "X-5217", "X-5218", "X-5224"] and move == 226 and _final(s, i, changes={
        "transactions": dict((k, {"reversed": True}) for k in extra),
        "accounts": _bal(i, {"A-2050": back - move, "A-2051": move})})


_add("T06", "bank", _bank(),
     "Noor Haddad's card was charged more than once in several shops. On her 'Main' checking account, go through "
     "the card payments since 8 September 2026: whenever the same merchant charged the same amount more than once "
     "on the same day, the first charge (lowest transaction id) is genuine and every further one is a duplicate. "
     "Reverse the duplicates, except any that has already been reversed. The same merchant and amount on different "
     "days is a normal repeat purchase and stays. When you are done, if the account balance is above 2,500, move "
     "the part above 2,500 to her 'Nest' savings account; otherwise move nothing.",
     [["find_customers", {"query": "Haddad"}], ["list_accounts", {"customer_id": "C-109"}],
      ["list_transactions", {"account_id": "A-2050", "type": "card"}],
      ["list_transactions", {"account_id": "A-2050", "type": "card", "page": 2}],
      ["list_transactions", {"account_id": "A-2050", "type": "card", "page": 3}],
      ["reverse_transaction", {"transaction_id": "X-5203"}], ["reverse_transaction", {"transaction_id": "X-5212"}],
      ["reverse_transaction", {"transaction_id": "X-5217"}], ["reverse_transaction", {"transaction_id": "X-5218"}],
      ["reverse_transaction", {"transaction_id": "X-5224"}], ["get_account", {"account_id": "A-2050"}],
      ["transfer", {"from_account": "A-2050", "to_account": "A-2051", "amount": 226}]],
     [["reverse_transaction", {"transaction_id": "X-5203"}], ["reverse_transaction", {"transaction_id": "X-5212"}],
      ["reverse_transaction", {"transaction_id": "X-5217"}], ["reverse_transaction", {"transaction_id": "X-5224"}],
      ["transfer", {"from_account": "A-2050", "to_account": "A-2051", "amount": 199}]],
     _c06, mentions=["Noor Haddad", "Main", "Nest"])


# --------------------------------------------------------------------------
# deploy fixture + tasks T07-T12
# --------------------------------------------------------------------------
def _pipe(mod=None):
    builds = {}
    for bid, svc, ver, status, scan, author, created, req, appr in [
        (101, "auth", "5.1.2", "passed", "clean", 5, "09-18", {}, [1, 2]),
        (102, "auth", "5.1.3", "passed", "clean", 5, "09-30", {}, [6, 8]),
        (103, "auth", "5.2.0", "failed", "pending", 7, "10-01", {}, []),
        (104, "auth", "5.2.1", "passed", "clean", 7, "10-02", {}, [3]),
        (111, "payments", "3.1.4", "passed", "clean", 9, "09-12", {}, [1, 2]),
        (112, "payments", "3.2.0", "passed", "clean", 9, "09-29", {"auth": "5.1.2"}, [1, 8]),
        (113, "payments", "3.2.1", "passed", "vulnerable", 7, "10-05", {}, []),
        (121, "checkout", "2.4.0", "passed", "clean", 7, "09-10", {}, [6, 2]),
        (122, "checkout", "2.4.1", "passed", "clean", 7, "09-24", {"payments": "3.1.4"}, [1, 8]),
        (123, "checkout", "2.5.0", "passed", "clean", 5, "10-02", {"payments": "3.2.0"}, [6]),
        (124, "checkout", "2.5.1", "passed", "vulnerable", 5, "10-05", {"payments": "3.2.0"}, []),
        (125, "checkout", "2.6.0", "failed", "pending", 7, "10-07", {}, []),
        (131, "catalog", "7.0.3", "passed", "clean", 9, "09-15", {}, [4]),
        (132, "catalog", "7.1.0", "passed", "clean", 7, "09-28", {}, [3]),
        (133, "catalog", "7.1.1", "passed", "clean", 9, "10-04", {}, []),
        (141, "search", "1.8.0", "passed", "clean", 5, "09-08", {}, [6]),
        (142, "search", "1.9.0", "passed", "clean", 9, "09-25", {}, [4, 6]),
        (143, "search", "1.9.1", "running", "pending", 9, "10-08", {}, []),
        (151, "catalog-ui", "4.2.0", "passed", "clean", 7, "09-11", {"search": "1.8.0"}, [1]),
        (152, "catalog-ui", "4.3.0", "passed", "clean", 5, "09-27", {"search": "1.9.0"}, [4]),
        (153, "catalog-ui", "4.3.1", "passed", "clean", 7, "10-03", {"search": "1.9.0"}, []),
        (161, "notify", "0.9.4", "passed", "clean", 9, "09-05", {}, [6]),
        (162, "notify", "0.9.5", "passed", "clean", 7, "09-27", {}, [3, 1]),
        (163, "notify", "1.0.0", "passed", "clean", 7, "09-30", {"auth": "5.2.1"}, [3]),
        (164, "notify", "1.0.1", "running", "pending", 5, "10-08", {}, []),
        (171, "reports", "2.2.0", "passed", "clean", 5, "09-02", {"search": "1.8.0"}, [4]),
        (172, "reports", "2.3.0", "passed", "clean", 7, "10-01", {"catalog": "7.1.0"}, [4]),
        (173, "reports", "2.3.1", "passed", "clean", 9, "10-06", {"catalog": "7.1.1"}, []),
        (174, "reports", "2.3.2", "failed", "pending", 9, "10-07", {}, []),
        (181, "ledger-sync", "1.4.0", "passed", "clean", 9, "09-20", {}, [3]),
        (182, "ledger-sync", "1.4.1", "passed", "clean", 5, "10-03", {"auth": "5.1.3"}, [3, 4]),
        (183, "ledger-sync", "1.5.0", "passed", "clean", 7, "10-04", {}, []),
    ]:
        builds["B-%d" % bid] = {"service": svc, "version": ver, "status": status, "scan": scan,
                                "author": "U-%02d" % author, "created": "2026-" + created, "requires": dict(req),
                                "approvals": ["U-%02d" % u for u in appr], "quarantined": False}

    def env(frozen, rows):
        return {"frozen": frozen, "deployed": dict((s, v[-1]) for s, v in rows.items()),
                "previous": dict((s, list(v[:-1])) for s, v in rows.items())}

    st = {
        "today": "2026-10-08",
        "users": {
            "U-01": {"name": "Priya Raman", "role": "approver", "team": "payments"},
            "U-02": {"name": "Owen Blake", "role": "release_manager", "team": "platform"},
            "U-03": {"name": "Dana Whitlock", "role": "dev", "team": "discovery"},
            "U-04": {"name": "Dana Whitmore", "role": "approver", "team": "discovery"},
            "U-05": {"name": "Jonas Feld", "role": "dev", "team": "identity"},
            "U-06": {"name": "Mei Tanaka", "role": "approver", "team": "identity"},
            "U-07": {"name": "Luca Moretti", "role": "dev", "team": "discovery"},
            "U-08": {"name": "Sara Lindholm", "role": "release_manager", "team": "platform"},
            "U-09": {"name": "Arjun Nair", "role": "dev", "team": "payments"},
        },
        "services": {
            "auth": {"tier": "critical", "team": "identity"},
            "payments": {"tier": "critical", "team": "payments"},
            "checkout": {"tier": "critical", "team": "payments"},
            "catalog": {"tier": "standard", "team": "discovery"},
            "search": {"tier": "standard", "team": "discovery"},
            "catalog-ui": {"tier": "standard", "team": "discovery"},
            "notify": {"tier": "standard", "team": "platform"},
            "reports": {"tier": "standard", "team": "platform"},
            "ledger-sync": {"tier": "standard", "team": "payments"},
        },
        "builds": builds,
        "environments": {
            # per service: history, oldest first; the last entry is what is deployed now
            "dev": env(False, {"auth": ["5.1.2", "5.1.3", "5.2.1"], "payments": ["3.1.4", "3.2.0"],
                               "checkout": ["2.4.0", "2.4.1", "2.5.0"], "catalog": ["7.0.3", "7.1.0", "7.1.1"],
                               "search": ["1.8.0", "1.9.0"], "catalog-ui": ["4.2.0", "4.3.0", "4.3.1"],
                               "notify": ["0.9.4", "0.9.5", "1.0.0"], "reports": ["2.2.0", "2.3.0"],
                               "ledger-sync": ["1.4.0", "1.4.1"]}),
            "staging": env(False, {"auth": ["5.1.2", "5.1.3"], "payments": ["3.1.4"], "checkout": ["2.4.0", "2.4.1"],
                                   "catalog": ["7.0.3", "7.1.0"], "search": ["1.8.0", "1.9.0"],
                                   "catalog-ui": ["4.2.0", "4.3.0"], "notify": ["0.9.4", "0.9.5"],
                                   "reports": ["2.2.0", "2.3.0"], "ledger-sync": ["1.4.0", "1.4.1"]}),
            "prod": env(False, {"auth": ["5.1.2"], "payments": ["3.1.4"], "checkout": ["2.4.0", "2.4.1"],
                                "catalog": ["7.0.3"], "search": ["1.8.0", "1.9.0"], "catalog-ui": ["4.2.0", "4.3.0"],
                                "notify": ["0.9.4"], "reports": ["2.2.0"], "ledger-sync": ["1.4.0"]}),
        },
    }
    if mod:
        mod(st)
    # sanity: every deployed version has a build and its requirements hold
    for e in _ENVS3:
        dep = st["environments"][e]["deployed"]
        for s, v in dep.items():
            b = [x for x in builds.values() if x["service"] == s and x["version"] == v]
            assert len(b) == 1, (e, s, v)
            for s2, mv in b[0]["requires"].items():
                assert _ver(dep[s2]) >= _ver(mv), (e, s, v, s2)
    return st


def _envs(i, upd):
    """environments changes: {env: {service: [new history...]}} -> full changes dict."""
    out = {}
    for e, rows in upd.items():
        out[e] = {"deployed": _mg(i["environments"][e]["deployed"], dict((s, v[-1]) for s, v in rows.items())),
                  "previous": _mg(i["environments"][e]["previous"], dict((s, list(v[:-1])) for s, v in rows.items()))}
    return out


_add("T07", "deploy", _pipe(),
     "Please get the newest checkout build that has passed CI and has a clean security scan live in production, "
     "going through the environments the way the release policy demands. If checkout needs a newer version of "
     "another service in some environment, bring that service up there to exactly the minimum version checkout "
     "requires, not to anything newer. Owen Blake has signed off on the checkout release verbally: record his "
     "approval on that build if production still needs one. Do not record any other approvals, do not touch the "
     "dev environment, and leave every other service where it is.",
     [["get_pipeline_info", {}], ["list_builds", {"service": "checkout"}], ["get_build", {"build_id": "B-123"}],
      ["get_service", {"service": "checkout"}], ["deploy", {"build_id": "B-123", "env": "staging"}],
      ["list_builds", {"service": "payments"}], ["deploy", {"build_id": "B-112", "env": "staging"}],
      ["deploy", {"build_id": "B-123", "env": "staging"}], ["list_users", {}],
      ["approve_build", {"build_id": "B-123", "approver_id": "U-02"}],
      ["deploy", {"build_id": "B-123", "env": "prod"}], ["deploy", {"build_id": "B-112", "env": "prod"}],
      ["deploy", {"build_id": "B-123", "env": "prod"}]],
     [["deploy", {"build_id": "B-124", "env": "dev"}], ["deploy", {"build_id": "B-112", "env": "staging"}],
      ["deploy", {"build_id": "B-124", "env": "staging"}],
      ["approve_build", {"build_id": "B-124", "approver_id": "U-02"}],
      ["deploy", {"build_id": "B-112", "env": "prod"}], ["deploy", {"build_id": "B-124", "env": "prod"}]],
     lambda s, i: _final(s, i, changes={
         "builds": {"B-123": {"approvals": _set(["U-06", "U-02"])}},
         "environments": _envs(i, {
             "staging": {"payments": ["3.1.4", "3.2.0"], "checkout": ["2.4.0", "2.4.1", "2.5.0"]},
             "prod": {"payments": ["3.1.4", "3.2.0"], "checkout": ["2.4.0", "2.4.1", "2.5.0"]}})}),
     ref_errors=[4, 10], mentions=["checkout", "Owen Blake"])


def _p08(st):
    st["environments"]["prod"]["frozen"] = True


_add("T08", "deploy", _pipe(_p08),
     "Production incident: search 1.9.0 is returning empty results. Roll search back in production to the version "
     "it ran before. If the pipeline refuses because another service in that environment needs the newer search, "
     "roll that other service back one step first - but only services that actually block you. Production is "
     "frozen at the moment and the freeze must stay on. After that, quarantine the bad search build so nobody can "
     "deploy it again; if the pipeline refuses that because the build is still live in some environment, deal with "
     "that environment in the same way as production. Finally remove every approval from the bad build. The dev "
     "environment must stay exactly as it is.",
     [["get_pipeline_info", {}], ["get_service", {"service": "search"}],
      ["rollback", {"service": "search", "env": "prod"}], ["rollback", {"service": "catalog-ui", "env": "prod"}],
      ["rollback", {"service": "search", "env": "prod"}], ["quarantine_build", {"build_id": "B-142"}],
      ["rollback", {"service": "search", "env": "staging"}], ["rollback", {"service": "catalog-ui", "env": "staging"}],
      ["rollback", {"service": "search", "env": "staging"}], ["quarantine_build", {"build_id": "B-142"}],
      ["get_build", {"build_id": "B-142"}],
      ["revoke_approval", {"build_id": "B-142", "approver_id": "U-04"}],
      ["revoke_approval", {"build_id": "B-142", "approver_id": "U-06"}]],
     [["rollback", {"service": "catalog-ui", "env": "prod"}], ["rollback", {"service": "search", "env": "prod"}],
      ["quarantine_build", {"build_id": "B-142"}],
      ["revoke_approval", {"build_id": "B-142", "approver_id": "U-04"}],
      ["revoke_approval", {"build_id": "B-142", "approver_id": "U-06"}]],
     lambda s, i: _final(s, i, changes={
         "builds": {"B-142": {"quarantined": True, "approvals": []}},
         "environments": _envs(i, {"prod": {"search": ["1.8.0"], "catalog-ui": ["4.2.0"]},
                                   "staging": {"search": ["1.8.0"], "catalog-ui": ["4.2.0"]}})}),
     ref_errors=[2, 5, 6], mentions=["search", "1.9.0"])


def _c09(s, i):
    hit = sorted(k for k, b in i["builds"].items()
                 if b["author"] == "U-07" and b["status"] == "passed" and "2026-09-28" <= b["created"] <= "2026-10-03")
    return hit == ["B-104", "B-132", "B-153", "B-163", "B-172"] and _final(s, i, changes={
        "builds": dict((k, {"quarantined": True}) for k in hit),
        "environments": _envs(i, {"staging": {"reports": ["2.2.0"], "catalog": ["7.0.3"]}})})


_add("T09", "deploy", _pipe(),
     "Luca Moretti's signing key was leaked. Every build he authored that was created from 28 September to "
     "3 October 2026 inclusive and passed CI has to be quarantined; his builds from outside that window are fine, "
     "and builds that did not pass cannot be deployed anyway, so leave those alone. If the pipeline refuses to "
     "quarantine one because it is live in an environment, roll that service back one step in that environment "
     "first, and if that rollback is refused because of another service, resolve it by rolling that other service "
     "back one step. Do not roll back anything you don't have to, and do not change production or any approvals.",
     [["list_users", {}], ["get_pipeline_info", {}], ["list_builds", {"author_id": "U-07", "status": "passed"}],
      ["list_builds", {"author_id": "U-07", "status": "passed", "page": 2}],
      ["quarantine_build", {"build_id": "B-104"}], ["quarantine_build", {"build_id": "B-153"}],
      ["quarantine_build", {"build_id": "B-163"}], ["quarantine_build", {"build_id": "B-132"}],
      ["rollback", {"service": "catalog", "env": "staging"}], ["rollback", {"service": "reports", "env": "staging"}],
      ["quarantine_build", {"build_id": "B-172"}], ["rollback", {"service": "catalog", "env": "staging"}],
      ["quarantine_build", {"build_id": "B-132"}]],
     [["quarantine_build", {"build_id": "B-104"}], ["quarantine_build", {"build_id": "B-153"}],
      ["quarantine_build", {"build_id": "B-163"}], ["rollback", {"service": "reports", "env": "staging"}],
      ["quarantine_build", {"build_id": "B-172"}], ["rollback", {"service": "catalog", "env": "staging"}],
      ["quarantine_build", {"build_id": "B-132"}], ["quarantine_build", {"build_id": "B-183"}]],
     _c09, ref_errors=[7, 8], mentions=["Luca Moretti"])


def _c10(s, i):
    return _final(s, i, changes={
        "builds": {"B-132": {"approvals": []}, "B-162": {"approvals": ["U-01"]}, "B-182": {"approvals": ["U-04"]}},
        "environments": _envs(i, {"prod": {"auth": ["5.1.2", "5.1.3"], "notify": ["0.9.4", "0.9.5"],
                                           "ledger-sync": ["1.4.0", "1.4.1"]}})})


_add("T10", "deploy", _pipe(),
     "Release sweep. Compare staging with production: for every service whose staging version is newer than its "
     "production version, promote the staging build to production if - and only if - it is ready under the release "
     "policy as things stand (approvals that count, scan, dependencies; a dependency may of course be satisfied by "
     "another promotion from this sweep). Builds that are not ready stay where they are: do not record new "
     "approvals for anything. Separately, tidy up the approvals on the builds that are currently deployed on "
     "staging: remove every approval that no longer counts under the policy, whether or not the build was "
     "promoted. Dev and staging deployments must not change.",
     [["get_pipeline_info", {}], ["list_users", {}], ["get_environment", {"env": "staging"}],
      ["get_environment", {"env": "prod"}], ["get_build", {"build_id": "B-102"}], ["get_build", {"build_id": "B-132"}],
      ["get_build", {"build_id": "B-162"}], ["get_build", {"build_id": "B-172"}], ["get_build", {"build_id": "B-182"}],
      ["deploy", {"build_id": "B-182", "env": "prod"}], ["deploy", {"build_id": "B-102", "env": "prod"}],
      ["deploy", {"build_id": "B-182", "env": "prod"}], ["deploy", {"build_id": "B-162", "env": "prod"}],
      ["revoke_approval", {"build_id": "B-132", "approver_id": "U-03"}],
      ["revoke_approval", {"build_id": "B-162", "approver_id": "U-03"}],
      ["revoke_approval", {"build_id": "B-182", "approver_id": "U-03"}]],
     [["deploy", {"build_id": "B-102", "env": "prod"}], ["deploy", {"build_id": "B-182", "env": "prod"}],
      ["deploy", {"build_id": "B-162", "env": "prod"}],
      ["revoke_approval", {"build_id": "B-132", "approver_id": "U-03"}],
      ["approve_build", {"build_id": "B-132", "approver_id": "U-04"}],
      ["deploy", {"build_id": "B-132", "env": "prod"}],
      ["revoke_approval", {"build_id": "B-162", "approver_id": "U-03"}],
      ["revoke_approval", {"build_id": "B-182", "approver_id": "U-03"}]],
     _c10, ref_errors=[9], mentions=["staging"])

_add("T11", "deploy", _pipe(),
     "Tomorrow's release train needs three services on staging: catalog, reports and notify. For each of them, "
     "staging should run its newest build that has passed CI and has a clean scan (builds still running or failed "
     "don't count). Do whatever the release policy requires to get them there, including on dev if a build is not "
     "on dev yet. If one of the three needs a newer version of some other service on staging, bring that other "
     "service up on staging to exactly the minimum version required, nothing newer. Production must not change, "
     "no approvals are to be recorded, and services outside this request stay as they are unless the pipeline "
     "forces a dependency as described.",
     [["get_pipeline_info", {}], ["list_builds", {"service": "catalog"}], ["list_builds", {"service": "reports"}],
      ["list_builds", {"service": "notify"}], ["get_environment", {"env": "dev"}],
      ["get_environment", {"env": "staging"}], ["deploy", {"build_id": "B-133", "env": "staging"}],
      ["deploy", {"build_id": "B-173", "env": "staging"}], ["deploy", {"build_id": "B-173", "env": "dev"}],
      ["deploy", {"build_id": "B-173", "env": "staging"}], ["deploy", {"build_id": "B-163", "env": "staging"}],
      ["get_build", {"build_id": "B-163"}], ["list_builds", {"service": "auth"}],
      ["deploy", {"build_id": "B-104", "env": "staging"}], ["deploy", {"build_id": "B-163", "env": "staging"}]],
     [["deploy", {"build_id": "B-133", "env": "staging"}], ["deploy", {"build_id": "B-173", "env": "dev"}],
      ["deploy", {"build_id": "B-173", "env": "staging"}]],
     lambda s, i: _final(s, i, changes={"environments": _envs(i, {
         "dev": {"reports": ["2.2.0", "2.3.0", "2.3.1"]},
         "staging": {"catalog": ["7.0.3", "7.1.0", "7.1.1"], "reports": ["2.2.0", "2.3.0", "2.3.1"],
                     "auth": ["5.1.2", "5.1.3", "5.2.1"], "notify": ["0.9.4", "0.9.5", "1.0.0"]}})}),
     ref_errors=[7, 10], mentions=["catalog", "reports", "notify"])


def _p12(st):
    st["builds"]["B-102"]["approvals"] = ["U-03", "U-08"]


_add("T12", "deploy", _pipe(_p12),
     "Dana Whitlock has moved to a developer role, so her approvals no longer count. Remove her approval from "
     "every build that has not reached production yet - a build counts as having reached production if its "
     "version is the one production runs now or an older one; those are history and stay untouched. Then look at "
     "the builds you just changed that are currently deployed on staging: any of them that is now short of the "
     "approvals production requires gets Mei Tanaka's approval, plus Sara Lindholm's only if a release-manager "
     "approval is still missing after that. Do not confuse her with Dana Whitmore, and do not deploy or roll back "
     "anything.",
     [["list_users", {}], ["get_pipeline_info", {}], ["list_builds", {"approved_by": "U-03"}],
      ["list_builds", {"approved_by": "U-03", "page": 2}], ["get_environment", {"env": "prod"}],
      ["get_environment", {"env": "staging"}],
      ["revoke_approval", {"build_id": "B-102", "approver_id": "U-03"}],
      ["revoke_approval", {"build_id": "B-104", "approver_id": "U-03"}],
      ["revoke_approval", {"build_id": "B-132", "approver_id": "U-03"}],
      ["revoke_approval", {"build_id": "B-162", "approver_id": "U-03"}],
      ["revoke_approval", {"build_id": "B-163", "approver_id": "U-03"}],
      ["revoke_approval", {"build_id": "B-182", "approver_id": "U-03"}],
      ["approve_build", {"build_id": "B-102", "approver_id": "U-06"}],
      ["approve_build", {"build_id": "B-132", "approver_id": "U-06"}]],
     [["revoke_approval", {"build_id": "B-102", "approver_id": "U-03"}],
      ["revoke_approval", {"build_id": "B-104", "approver_id": "U-03"}],
      ["revoke_approval", {"build_id": "B-132", "approver_id": "U-03"}],
      ["revoke_approval", {"build_id": "B-162", "approver_id": "U-03"}],
      ["revoke_approval", {"build_id": "B-163", "approver_id": "U-03"}],
      ["revoke_approval", {"build_id": "B-182", "approver_id": "U-03"}],
      ["revoke_approval", {"build_id": "B-181", "approver_id": "U-03"}],
      ["approve_build", {"build_id": "B-102", "approver_id": "U-06"}],
      ["approve_build", {"build_id": "B-132", "approver_id": "U-06"}]],
     lambda s, i: _final(s, i, changes={"builds": {
         "B-102": {"approvals": _set(["U-08", "U-06"])}, "B-104": {"approvals": []},
         "B-132": {"approvals": ["U-06"]}, "B-162": {"approvals": ["U-01"]}, "B-163": {"approvals": []},
         "B-182": {"approvals": ["U-04"]}}}),
     mentions=["Dana Whitlock", "Dana Whitmore", "Mei Tanaka", "Sara Lindholm"])


# --------------------------------------------------------------------------
# registrar fixture + tasks T13-T18
# --------------------------------------------------------------------------
def _reg():
    courses = {}
    for cid, title, cr, dept, pre in [
        ("MATH101", "Calculus I", 4, "MATH", []), ("MATH201", "Calculus II", 4, "MATH", ["MATH101"]),
        ("MATH220", "Linear Algebra", 3, "MATH", ["MATH101"]), ("STAT230", "Probability and Statistics", 3, "STAT", ["MATH101"]),
        ("CS110", "Introduction to Programming", 4, "CS", []), ("CS210", "Data Structures", 4, "CS", ["CS110"]),
        ("CS310", "Algorithms", 3, "CS", ["CS210", "MATH220"]), ("CHEM110", "General Chemistry", 4, "CHEM", []),
        ("CHEM220", "Organic Chemistry", 4, "CHEM", ["CHEM110"]), ("PHYS210", "Mechanics", 4, "PHYS", ["MATH101"]),
        ("HIST105", "World History", 3, "HIST", []), ("PHIL120", "Logic", 3, "PHIL", []),
        ("ECON101", "Microeconomics", 3, "ECON", []), ("ART150", "Drawing", 2, "ART", []),
        ("MUS140", "Music Theory", 2, "MUS", []),
    ]:
        courses[cid] = {"title": title, "credits": cr, "dept": dept, "prereqs": pre}
    students = {}
    for n, name, year, dept, done, holds in [
        (1, "Aiko Tanabe", 3, "PHYS", {"MATH101": "A", "CHEM110": "A"}, []),
        (2, "Ben Okafor", 2, "CHEM", {"MATH101": "B", "CHEM110": "C-"}, []),
        (3, "Carla Mendes", 4, "PHYS", {"MATH101": "A-", "CHEM110": "B"}, []),
        (4, "Dmitri Volkov", 3, "CHEM", {"MATH101": "B", "CHEM110": "B+", "CS110": "B"}, []),
        (5, "Elena Rossi", 2, "BIO", {"MATH101": "C+"}, []),
        (6, "Amara Okoye", 3, "CS", {"MATH101": "A", "CS110": "A", "CS210": "A-", "MATH220": "B+"}, []),
        (7, "Farid Haddad", 2, "CHEM", {"MATH101": "C", "CHEM110": "C", "CS110": "B-"}, []),
        (8, "Greta Lindahl", 3, "BIO", {"MATH101": "B", "CHEM110": "W"}, []),
        (9, "Hugo Marchand", 3, "PHYS", {"MATH101": "B+", "CHEM110": "C-"}, []),
        (10, "Felix Brandt", 3, "CHEM", {"MATH101": "B", "CHEM110": "B", "CS110": "C+"}, []),
        (11, "Ines Carvalho", 2, "CHEM", {"MATH101": "B-", "CHEM110": "C+"}, []),
        (12, "Jonas Weber", 4, "PHYS", {"MATH101": "C", "CHEM110": "D"}, []),
        (13, "Keiko Mori", 2, "BIO", {"MATH101": "A-", "CHEM110": "I"}, []),
        (14, "Liam O'Connor", 3, "CHEM", {"MATH101": "B", "CHEM110": "A-", "CS110": "B"}, []),
        (15, "Mila Petrova", 1, "PHYS", {"MATH101": "A"}, []),
        (16, "Nikhil Rao", 2, "PHYS", {"MATH101": "B+", "CHEM110": "B-", "CS110": "A"}, []),
        (17, "Lena Fischer", 2, "MATH", {"MATH101": "A", "CHEM110": "F"}, []),
        (18, "Omar Suleiman", 3, "PHYS", {"MATH101": "B"}, []),
        (19, "Kofi Mensah", 3, "MATH", {"MATH101": "A-", "CHEM110": "C", "CS110": "B+"}, []),
        (20, "Petra Novotna", 2, "PHYS", {"MATH101": "A", "CHEM110": "A", "CS110": "B"}, []),
        (21, "Quentin Dubois", 2, "PHYS", {"MATH101": "C+"}, []),
        (22, "Rosa Jimenez", 2, "ECON", {"MATH101": "B", "CHEM110": "C"}, []),
        (23, "Stefan Kowalski", 2, "ECON", {"MATH101": "B-"}, ["financial"]),
        (24, "Tara Singh", 2, "CS", {"MATH101": "B+", "CS110": "A-"}, []),
        (25, "Uma Krishnan", 1, "ECON", {"MATH101": "A"}, []),
        (26, "Viktor Hahn", 3, "ECON", {"MATH101": "C", "CS110": "C"}, []),
        (27, "Yara Novak", 2, "CS", {"CS110": "B", "MATH101": "C-"}, []),
        (28, "Yara Nowak", 1, "HIST", {}, []),
        (29, "Wen Li", 4, "MATH", {"MATH101": "A"}, []),
        (30, "Zofia Kaminska", 3, "MATH", {"MATH101": "B+"}, []),
        (31, "Bao Tran", 2, "MATH", {"MATH101": "B"}, []),
        (32, "Chiara Bellini", 2, "MATH", {"MATH101": "A-"}, []),
        (33, "Felix Brandl", 1, "HIST", {}, []),
        (34, "Esme Laurent", 1, "BIO", {}, []),
        (35, "Finn Aalto", 1, "CS", {}, []),
        (36, "Hana Sato", 3, "MATH", {"MATH101": "A"}, []),
    ]:
        students["S-%02d" % n] = {"name": name, "year": year, "dept": dept, "completed": done, "holds": holds}
    sections = {}
    for sec, days, start, end, room, cap, enrolled, wl in [
        ("CS110-A", "tue,thu", "08:30", "10:00", "AUD-A", 12, [2, 5, 13, 8], []),
        ("MATH101-A", "mon,wed,fri", "09:00", "10:00", "R-203", 12, [28, 33, 34], []),
        ("MATH101-B", "tue,thu", "10:00", "11:30", "R-203", 12, [27, 35], []),
        ("MATH201-A", "mon,wed,fri", "08:00", "09:00", "R-101", 8, [10, 22, 25, 31], []),
        ("MATH201-B", "tue,thu", "15:00", "16:30", "R-101", 8, [6, 19, 32, 21], []),
        ("MATH220-A", "mon,wed", "11:00", "12:30", "R-101", 4, [19, 29, 30, 36], [18]),
        ("MATH220-B", "tue,thu", "09:00", "10:30", "R-101", 4, [17, 23, 31, 32], []),
        ("STAT230-A", "tue,thu", "09:00", "10:30", "R-202", 8, [6, 3, 9, 12, 15, 18, 21, 30], [22, 23, 24, 25, 26]),
        ("CS210-A", "mon,wed", "10:00", "11:30", "R-301", 4, [10, 4, 7, 26], [27, 24]),
        ("CS210-B", "tue,thu", "13:00", "14:30", "R-301", 8, [19, 16, 20, 14], []),
        ("CS310-A", "mon,wed", "11:00", "12:30", "R-302", 9, [6], []),
        ("CHEM110-A", "mon,wed", "13:00", "15:00", "LAB-1", 6, [28, 25, 31, 32, 24, 30], []),
        ("CHEM110-B", "tue,thu", "15:00", "17:00", "LAB-1", 8, [29, 23, 35], []),
        ("CHEM220-A", "tue,thu", "10:00", "12:00", "LAB-1", 10, [1, 2, 4, 5, 7, 8, 10, 11, 13, 14], [16, 17, 19, 20]),
        ("PHYS210-A", "mon,wed", "10:00", "11:30", "R-201", 9, [1, 2, 5, 8, 11, 13, 14, 16, 20], []),
        ("PHYS210-B", "tue,thu", "14:00", "15:30", "R-102", 5, [3, 9, 12, 15, 18], [21]),
        ("HIST105-A", "mon,wed", "10:30", "11:30", "R-203", 10, [12, 27, 22, 23, 25, 28], []),
        ("HIST105-B", "tue,thu", "11:00", "12:30", "R-302", 8, [6, 19, 26, 21], []),
        ("PHIL120-A", "fri", "09:30", "12:00", "R-302", 6, [6, 2, 8, 13, 16, 26], [24, 25]),
        ("PHIL120-B", "mon,wed", "14:00", "15:30", "R-102", 6, [10, 19, 1, 3, 11, 22], [9]),
        ("ECON101-A", "fri", "13:00", "16:00", "AUD-A", 10, [17, 22, 23, 25, 26], []),
        ("ECON101-B", "mon,wed", "10:00", "11:30", "R-102", 8, [31, 32], []),
        ("ART150-A", "thu", "15:00", "17:00", "LAB-2", 5, [1, 5, 8, 13, 2], [10]),
        ("ART150-B", "wed", "10:00", "12:00", "LAB-2", 6, [17], []),
        ("MUS140-A", "fri", "09:00", "11:00", "LAB-2", 8, [27, 20, 14], []),
    ]:
        sections[sec] = {"course": sec.split("-")[0], "days": days.split(","), "start": start, "end": end, "room": room,
                         "capacity": cap, "enrolled": ["S-%02d" % n for n in enrolled],
                         "waitlist": ["S-%02d" % n for n in wl], "status": "open"}
    st = {"today": "2026-10-08", "term": "Spring 2027 (registration open)",
          "policy": {"max_credits": 18, "passing": ["A", "A-", "B+", "B", "B-", "C+", "C"]},
          "courses": courses,
          "rooms": {"AUD-A": 40, "R-203": 20, "R-201": 12, "R-301": 11, "R-102": 10, "R-101": 10, "R-302": 9,
                    "R-202": 8, "LAB-1": 10, "LAB-2": 8},
          "students": students, "sections": sections}
    # sanity: the fixture itself obeys the rules (except the CHEM220 prerequisite, which T14 is about)
    env = RegistrarEnv(st)
    for k, s in sections.items():
        assert len(s["enrolled"]) <= s["capacity"] <= st["rooms"][s["room"]], k
        assert not s["waitlist"] or len(s["enrolled"]) == s["capacity"], k
        assert not set(s["enrolled"]) & set(s["waitlist"]), k
        for k2, s2 in sections.items():
            assert k2 == k or s2["room"] != s["room"] or not env._overlap(s, s2), (k, k2)
        for sid in s["enrolled"]:
            assert env._clash(sid, k) is None, (sid, k, env._clash(sid, k))
            assert s["course"] == "CHEM220" or env._prereq_gap(sid, s["course"]) is None, (sid, k)
    for sid in students:
        assert env._credits(sid) <= 18, sid
        mine = [sections[k]["course"] for k in env._mine(sid)]
        assert len(mine) == len(set(mine)), sid
    return st


def _sec(i, upd):
    """sections changes: {section: {"add": [...], "rem": [...], "waitlist": [...], other fields}}"""
    out = {}
    for k, ch in upd.items():
        ch = dict(ch)
        add, rem = ch.pop("add", []), ch.pop("rem", [])
        if add or rem:
            ch["enrolled"] = _set([x for x in i["sections"][k]["enrolled"] if x not in rem] + list(add))
        out[k] = ch
    return {"sections": out}


_add("T13", "registrar", _reg(),
     "PHYS210-B is being cancelled and its people go to PHYS210-A as far as possible. First raise PHYS210-A's "
     "capacity as far as its room allows. Then take the students enrolled in PHYS210-B in priority order - higher "
     "year first, ties broken by the lower student id - and move each one into PHYS210-A. A student whose timetable "
     "clashes with PHYS210-A cannot be moved and is simply dropped from PHYS210-B. Once PHYS210-A is full, the "
     "students still left are dropped from PHYS210-B and put on PHYS210-A's waitlist, still in priority order. "
     "After them, whoever is on PHYS210-B's own waitlist goes to the end of PHYS210-A's waitlist. Finally cancel "
     "PHYS210-B. Nothing else should change.",
     [["get_term_info", {}], ["get_section", {"section_id": "PHYS210-B"}], ["get_section", {"section_id": "PHYS210-A"}],
      ["set_capacity", {"section_id": "PHYS210-A", "capacity": 12}],
      ["swap_section", {"student_id": "S-03", "from_section": "PHYS210-B", "to_section": "PHYS210-A"}],
      ["swap_section", {"student_id": "S-12", "from_section": "PHYS210-B", "to_section": "PHYS210-A"}],
      ["drop", {"student_id": "S-12", "section_id": "PHYS210-B"}],
      ["swap_section", {"student_id": "S-09", "from_section": "PHYS210-B", "to_section": "PHYS210-A"}],
      ["swap_section", {"student_id": "S-18", "from_section": "PHYS210-B", "to_section": "PHYS210-A"}],
      ["drop", {"student_id": "S-15", "section_id": "PHYS210-B"}],
      ["join_waitlist", {"student_id": "S-15", "section_id": "PHYS210-A"}],
      ["leave_waitlist", {"student_id": "S-21", "section_id": "PHYS210-B"}],
      ["join_waitlist", {"student_id": "S-21", "section_id": "PHYS210-A"}],
      ["cancel_section", {"section_id": "PHYS210-B"}]],
     [["set_capacity", {"section_id": "PHYS210-A", "capacity": 12}],
      ["swap_section", {"student_id": "S-03", "from_section": "PHYS210-B", "to_section": "PHYS210-A"}],
      ["swap_section", {"student_id": "S-09", "from_section": "PHYS210-B", "to_section": "PHYS210-A"}],
      ["swap_section", {"student_id": "S-15", "from_section": "PHYS210-B", "to_section": "PHYS210-A"}],
      ["drop", {"student_id": "S-12", "section_id": "PHYS210-B"}],
      ["drop", {"student_id": "S-18", "section_id": "PHYS210-B"}],
      ["join_waitlist", {"student_id": "S-18", "section_id": "PHYS210-A"}],
      ["leave_waitlist", {"student_id": "S-21", "section_id": "PHYS210-B"}],
      ["join_waitlist", {"student_id": "S-21", "section_id": "PHYS210-A"}],
      ["cancel_section", {"section_id": "PHYS210-B"}]],
     lambda s, i: _final(s, i, changes=_sec(i, {
         "PHYS210-A": {"capacity": 12, "add": ["S-03", "S-09", "S-18"], "waitlist": ["S-15", "S-21"]},
         "PHYS210-B": {"enrolled": [], "waitlist": [], "status": "cancelled"}})),
     ref_errors=[5], mentions=["PHYS210-A", "PHYS210-B"], seq=[[10, 12]])


def _c14(s, i):
    ok = i["policy"]["passing"]
    sec = i["sections"]["CHEM220-A"]
    bad = [x for x in sec["enrolled"] if i["students"][x]["completed"].get("CHEM110") not in ok]
    badw = [x for x in sec["waitlist"] if i["students"][x]["completed"].get("CHEM110") not in ok]
    return sorted(bad) == ["S-02", "S-05", "S-08", "S-13"] and badw == ["S-17"] and _final(s, i, changes=_sec(i, {
        "CHEM220-A": {"rem": bad, "add": ["S-16", "S-20"], "waitlist": ["S-19"]}}))


_add("T14", "registrar", _reg(),
     "The prerequisite check for CHEM220 was switched off during early registration, so CHEM220-A has to be "
     "audited. Use the grade rule from the registration policy. Drop every student enrolled in CHEM220-A who does "
     "not meet the CHEM110 prerequisite, and take anyone who does not meet it off that section's waitlist as well. "
     "Then fill the freed seats from the waitlist in waitlist order. If the system refuses to enroll a waitlisted "
     "student for some other reason, leave that student on the waitlist where they are and carry on with the next "
     "one. Seats that cannot be filled stay empty. Do not change the capacity or any other section.",
     [["get_term_info", {}], ["get_section", {"section_id": "CHEM220-A"}],
      ["list_grades", {"course_id": "CHEM110"}], ["list_grades", {"course_id": "CHEM110", "page": 2}],
      ["list_grades", {"course_id": "CHEM110", "page": 3}],
      ["drop", {"student_id": "S-02", "section_id": "CHEM220-A"}], ["drop", {"student_id": "S-05", "section_id": "CHEM220-A"}],
      ["drop", {"student_id": "S-08", "section_id": "CHEM220-A"}], ["drop", {"student_id": "S-13", "section_id": "CHEM220-A"}],
      ["leave_waitlist", {"student_id": "S-17", "section_id": "CHEM220-A"}],
      ["enroll", {"student_id": "S-16", "section_id": "CHEM220-A"}],
      ["enroll", {"student_id": "S-19", "section_id": "CHEM220-A"}],
      ["enroll", {"student_id": "S-20", "section_id": "CHEM220-A"}]],
     [["drop", {"student_id": "S-05", "section_id": "CHEM220-A"}], ["drop", {"student_id": "S-08", "section_id": "CHEM220-A"}],
      ["drop", {"student_id": "S-13", "section_id": "CHEM220-A"}],
      ["leave_waitlist", {"student_id": "S-17", "section_id": "CHEM220-A"}],
      ["enroll", {"student_id": "S-16", "section_id": "CHEM220-A"}],
      ["enroll", {"student_id": "S-20", "section_id": "CHEM220-A"}]],
     _c14, ref_errors=[11], mentions=["CHEM220-A", "CHEM110", "CHEM220"])

_add("T15", "registrar", _reg(),
     "The waitlist for STAT230-A is long, so we are giving the section more room. Move STAT230-A into the largest "
     "room that is free at its meeting time on all of its days (a room is not free if any other section uses it "
     "at an overlapping time), then set the section's capacity to exactly that room's capacity. After that, "
     "enroll students from its waitlist strictly in waitlist order for as long as there are free seats. If the "
     "system refuses someone, that person stays on the waitlist in place and you continue with the next one. "
     "Do not change any other section or anyone's other enrolments.",
     [["get_section", {"section_id": "STAT230-A"}], ["get_term_info", {}],
      ["list_sections", {"day": "tue"}], ["list_sections", {"day": "tue", "page": 2}],
      ["change_room", {"section_id": "STAT230-A", "room_id": "AUD-A"}],
      ["change_room", {"section_id": "STAT230-A", "room_id": "R-203"}],
      ["change_room", {"section_id": "STAT230-A", "room_id": "R-201"}],
      ["set_capacity", {"section_id": "STAT230-A", "capacity": 12}],
      ["enroll", {"student_id": "S-22", "section_id": "STAT230-A"}], ["enroll", {"student_id": "S-23", "section_id": "STAT230-A"}],
      ["enroll", {"student_id": "S-24", "section_id": "STAT230-A"}], ["enroll", {"student_id": "S-25", "section_id": "STAT230-A"}],
      ["enroll", {"student_id": "S-26", "section_id": "STAT230-A"}]],
     [["change_room", {"section_id": "STAT230-A", "room_id": "R-201"}],
      ["set_capacity", {"section_id": "STAT230-A", "capacity": 12}],
      ["enroll", {"student_id": "S-22", "section_id": "STAT230-A"}]],
     lambda s, i: _final(s, i, changes=_sec(i, {"STAT230-A": {
         "room": "R-201", "capacity": 12, "add": ["S-22", "S-24", "S-25", "S-26"], "waitlist": ["S-23"]}})),
     ref_errors=[4, 5, 9], mentions=["STAT230-A"])

_add("T16", "registrar", _reg(),
     "Yara Novak (the second-year CS student, not Yara Nowak) has an advising plan with five courses to add: CS210, "
     "MATH220, PHIL120, ECON101 and ART150. Her current enrolments stay as they are. For each course on the plan: "
     "if she does not meet the prerequisites, skip the course completely. Otherwise look only at the sections "
     "that do not clash with her current timetable: enroll her if such a section has a free seat, and if the "
     "only clash-free section is full, put her on that section's waitlist. Never put her on the waitlist of a "
     "section that clashes with her timetable, and once she is enrolled in a course she should no longer be on "
     "any waitlist for that same course.",
     [["find_students", {"query": "Yara"}], ["get_student", {"student_id": "S-27"}], ["get_term_info", {}],
      ["list_sections", {"course_id": "CS210"}], ["list_sections", {"course_id": "MATH220"}],
      ["list_sections", {"course_id": "PHIL120"}], ["list_sections", {"course_id": "ECON101"}],
      ["list_sections", {"course_id": "ART150"}],
      ["enroll", {"student_id": "S-27", "section_id": "CS210-B"}],
      ["leave_waitlist", {"student_id": "S-27", "section_id": "CS210-A"}],
      ["enroll", {"student_id": "S-27", "section_id": "MATH220-B"}],
      ["join_waitlist", {"student_id": "S-27", "section_id": "PHIL120-B"}],
      ["enroll", {"student_id": "S-27", "section_id": "ECON101-A"}],
      ["join_waitlist", {"student_id": "S-27", "section_id": "ART150-A"}]],
     [["enroll", {"student_id": "S-27", "section_id": "CS210-B"}],
      ["leave_waitlist", {"student_id": "S-27", "section_id": "CS210-A"}],
      ["join_waitlist", {"student_id": "S-27", "section_id": "MATH220-B"}],
      ["join_waitlist", {"student_id": "S-27", "section_id": "PHIL120-B"}],
      ["enroll", {"student_id": "S-27", "section_id": "ECON101-A"}],
      ["join_waitlist", {"student_id": "S-27", "section_id": "ART150-A"}]],
     lambda s, i: _final(s, i, changes=_sec(i, {
         "CS210-B": {"add": ["S-27"]}, "CS210-A": {"waitlist": ["S-24"]},
         "PHIL120-B": {"waitlist": ["S-09", "S-27"]}, "ECON101-A": {"add": ["S-27"]},
         "ART150-A": {"waitlist": ["S-10", "S-27"]}})),
     ref_errors=[10], mentions=["Yara Novak", "Yara Nowak", "CS210", "MATH220", "PHIL120", "ECON101", "ART150"])

_add("T17", "registrar", _reg(),
     "Felix Brandt (third-year chemistry; there is another student with a very similar name) is withdrawing from "
     "the university. Drop him from every section he is enrolled in and take him off every waitlist he is on. "
     "Then, for each section he was enrolled in that has a waitlist, offer the seat he freed to that waitlist in "
     "order: the first waitlisted student whom the system accepts gets enrolled, and anyone the system refuses "
     "stays on the waitlist in place. Only the one freed seat per section is given away. Sections without a "
     "waitlist just keep the empty seat. Nobody else's enrolments should change.",
     [["find_students", {"query": "Felix"}], ["get_student", {"student_id": "S-10"}],
      ["drop", {"student_id": "S-10", "section_id": "CHEM220-A"}], ["drop", {"student_id": "S-10", "section_id": "CS210-A"}],
      ["drop", {"student_id": "S-10", "section_id": "MATH201-A"}], ["drop", {"student_id": "S-10", "section_id": "PHIL120-B"}],
      ["leave_waitlist", {"student_id": "S-10", "section_id": "ART150-A"}],
      ["get_section", {"section_id": "CHEM220-A"}], ["enroll", {"student_id": "S-16", "section_id": "CHEM220-A"}],
      ["get_section", {"section_id": "CS210-A"}], ["enroll", {"student_id": "S-27", "section_id": "CS210-A"}],
      ["enroll", {"student_id": "S-24", "section_id": "CS210-A"}],
      ["get_section", {"section_id": "PHIL120-B"}], ["enroll", {"student_id": "S-09", "section_id": "PHIL120-B"}]],
     [["drop", {"student_id": "S-10", "section_id": "CHEM220-A"}], ["drop", {"student_id": "S-10", "section_id": "CS210-A"}],
      ["drop", {"student_id": "S-10", "section_id": "MATH201-A"}], ["drop", {"student_id": "S-10", "section_id": "PHIL120-B"}],
      ["enroll", {"student_id": "S-16", "section_id": "CHEM220-A"}],
      ["enroll", {"student_id": "S-24", "section_id": "CS210-A"}],
      ["enroll", {"student_id": "S-09", "section_id": "PHIL120-B"}]],
     lambda s, i: _final(s, i, changes=_sec(i, {
         "CHEM220-A": {"rem": ["S-10"], "add": ["S-16"], "waitlist": ["S-17", "S-19", "S-20"]},
         "CS210-A": {"rem": ["S-10"], "add": ["S-24"], "waitlist": ["S-27"]},
         "MATH201-A": {"rem": ["S-10"]},
         "PHIL120-B": {"rem": ["S-10"], "add": ["S-09"], "waitlist": []},
         "ART150-A": {"waitlist": []}})),
     ref_errors=[10], mentions=["Felix Brandt"])

_add("T18", "registrar", _reg(),
     "Amara Okoye needs CHEM110 this term and wants a real seat, not a waitlist place. Adding it would take her "
     "over the credit limit, so first drop one course to make room: among her current courses outside her own "
     "department, the one with the fewest credits, and if several tie, the one whose section has the longest "
     "waitlist. Then enroll her in a CHEM110 section with a free seat. If that section clashes with one of her "
     "remaining courses and that course has another section that fits her timetable and has a seat, switch her "
     "to that other section instead of dropping anything else. Finally, give the seat she gave up in the dropped "
     "course to the first person on that section's waitlist whom the system accepts.",
     [["find_students", {"query": "Okoye"}], ["get_student", {"student_id": "S-06"}], ["get_term_info", {}],
      ["list_sections", {"course_id": "CHEM110"}], ["list_sections", {"course_id": "STAT230"}],
      ["list_sections", {"course_id": "HIST105"}], ["list_sections", {"course_id": "PHIL120"}],
      ["drop", {"student_id": "S-06", "section_id": "STAT230-A"}],
      ["enroll", {"student_id": "S-06", "section_id": "CHEM110-B"}], ["list_sections", {"course_id": "MATH201"}],
      ["swap_section", {"student_id": "S-06", "from_section": "MATH201-B", "to_section": "MATH201-A"}],
      ["enroll", {"student_id": "S-06", "section_id": "CHEM110-B"}], ["get_section", {"section_id": "STAT230-A"}],
      ["enroll", {"student_id": "S-22", "section_id": "STAT230-A"}]],
     [["drop", {"student_id": "S-06", "section_id": "HIST105-B"}],
      ["swap_section", {"student_id": "S-06", "from_section": "MATH201-B", "to_section": "MATH201-A"}],
      ["enroll", {"student_id": "S-06", "section_id": "CHEM110-B"}]],
     lambda s, i: _final(s, i, changes=_sec(i, {
         "STAT230-A": {"rem": ["S-06"], "add": ["S-22"], "waitlist": ["S-23", "S-24", "S-25", "S-26"]},
         "MATH201-B": {"rem": ["S-06"]}, "MATH201-A": {"add": ["S-06"]}, "CHEM110-B": {"add": ["S-06"]}})),
     ref_errors=[8], mentions=["Amara Okoye", "CHEM110"])


# --------------------------------------------------------------------------
# fleet fixture + tasks T19-T24
# --------------------------------------------------------------------------
_FLEET_JOBS = {
    # (id, date, start, end, customer, load_kg, requires, priority, vehicle, driver[, status])
    "NORTH_A": [
        (101, "10-08", 13, 16, "Kessler Bau", 2800, "none", "normal", 4, 5),
        (102, "10-09", 8, 11, "Hafen Logistik", 3400, "none", "normal", 4, 5),
        (103, "10-09", 12, 15, "Chemie Nordpark", 1300, "hazmat", "high", 4, 4),
        (104, "10-13", 9, 12, "Kessler Bau", 4200, "none", "normal", 4, 5),
        (105, "10-07", 9, 12, "Kessler Bau", 3900, "none", "normal", 4, 5, "done"),
        (110, "10-08", 14, 17, "Frischemarkt Nord", 2100, "reefer", "normal", 5, 1),
        (111, "10-09", 8, 10, "Moebel Jansen", 1000, "none", "low", 1, 2),
        (112, "10-09", 13, 16, "Stahlwerk Elbe", 6000, "none", "normal", 7, 3),
        (113, "10-08", 9, 12, "Moebel Jansen", 900, "none", "normal", 2, 2)],
    "NORTH_B": [
        (130, "10-09", 7, 10, "Norlund Foods", 2600, "reefer", "normal", 6, 1),
        (131, "10-09", 11, 13, "Norlund Foods", 900, "none", "normal", 1, 2),
        (132, "10-09", 14, 17, "Norlund Foods", 1900, "reefer", "high", 5, 4),
        (133, "10-09", 9, 11, "Norlund Foods", 700, "none", "low", 0, 0),
        (134, "10-09", 10, 12, "Norlund Marine", 1100, "none", "normal", 2, 5),
        (135, "10-10", 8, 10, "Norlund Foods", 800, "none", "normal", 1, 2),
        (136, "10-09", 15, 17, "Norlund Foods", 500, "none", "low", 0, 0, "cancelled"),
        (137, "10-12", 13, 15, "Kessler Bau", 3000, "none", "normal", 3, 4),
        (138, "10-09", 8, 12, "Kessler Bau", 2500, "none", "normal", 3, 3),
        (139, "10-12", 8, 10, "Moebel Jansen", 1000, "none", "normal", 2, 2),
        (140, "10-09", 16, 18, "Hafen Logistik", 1200, "none", "normal", 2, 5),
        (141, "10-09", 6, 8, "Frischemarkt Nord", 1500, "reefer", "normal", 5, 4)],
    "NORTH_C": [
        (160, "10-09", 7, 10, "Frischemarkt Nord", 2200, "reefer", "normal", 5, 1),
        (161, "10-09", 11, 13, "Kessler Bau", 3100, "none", "normal", 3, 1),
        (162, "10-09", 15, 18, "Moebel Jansen", 800, "none", "low", 1, 1),
        (163, "10-09", 13, 15, "Chemie Nordpark", 1500, "hazmat", "high", 4, 4),
        (164, "10-09", 8, 14, "Stahlwerk Elbe", 6500, "none", "normal", 7, 3),
        (165, "10-09", 14, 18, "Hafen Logistik", 3000, "none", "normal", 6, 5),
        (166, "10-09", 8, 16, "Moebel Jansen", 1100, "none", "normal", 2, 2),
        (167, "10-10", 8, 11, "Frischemarkt Nord", 2000, "reefer", "normal", 5, 1),
        (168, "10-08", 10, 12, "Moebel Jansen", 600, "none", "low", 1, 1)],
    "SOUTH_A": [
        (120, "10-09", 8, 12, "Fischkontor Sued", 2200, "reefer", "normal", 0, 0),
        (121, "10-09", 9, 13, "Betonwerk Sued", 5500, "none", "high", 0, 0),
        (122, "10-09", 10, 14, "Lackfabrik Mertens", 900, "hazmat", "normal", 0, 0),
        (123, "10-09", 14, 18, "Buerobedarf Kranz", 1450, "none", "low", 0, 0),
        (125, "10-09", 15, 17, "Getraenke Paulsen", 3000, "none", "normal", 10, 9),
        (126, "10-09", 14, 16, "Betonwerk Sued", 6000, "none", "normal", 12, 6),
        (127, "10-09", 13, 17, "Buerobedarf Kranz", 700, "none", "normal", 8, 7),
        (128, "10-09", 7, 9, "Getraenke Paulsen", 800, "none", "normal", 9, 7),
        (129, "10-09", 18, 20, "Fischkontor Sued", 1800, "reefer", "normal", 11, 9)],
    "SOUTH_B": [
        (170, "10-09", 9, 11, "Buerobedarf Kranz", 500, "none", "normal", 8, 7),
        (171, "10-12", 8, 10, "Buerobedarf Kranz", 600, "none", "normal", 8, 7),
        (172, "10-12", 11, 14, "Getraenke Paulsen", 950, "none", "normal", 8, 7),
        (173, "10-13", 9, 12, "Lackfabrik Mertens", 800, "none", "normal", 8, 8),
        (174, "10-14", 10, 12, "Buerobedarf Kranz", 1000, "none", "low", 8, 7),
        (175, "10-12", 12, 15, "Fischkontor Sued", 1200, "none", "normal", 9, 9),
        (176, "10-13", 13, 16, "Getraenke Paulsen", 1400, "none", "normal", 9, 7),
        (177, "10-14", 8, 10, "Fischkontor Sued", 900, "none", "normal", 9, 9),
        (178, "10-13", 14, 16, "Lackfabrik Mertens", 700, "none", "normal", 8, 8)],
    "EAST_A": [
        (150, "10-09", 9, 12, "Apotheken Ring Ost", 1500, "reefer", "low", 20, 13),
        (151, "10-09", 10, 12, "Frischemarkt Ost", 2000, "reefer", "high", 19, 10),
        (180, "10-12", 9, 12, "Stahlhandel Ost", 6800, "none", "normal", 18, 11),
        (181, "10-12", 11, 14, "Baumarkt Ost", 3900, "none", "normal", 15, 10),
        (182, "10-13", 8, 10, "Baumarkt Ost", 900, "none", "normal", 13, 12),
        (183, "10-09", 8, 10, "Baumarkt Ost", 1000, "none", "normal", 13, 12),
        (184, "10-09", 13, 16, "Stahlhandel Ost", 5000, "none", "normal", 18, 11),
        (185, "10-09", 14, 16, "Frischemarkt Ost", 1200, "reefer", "normal", 19, 10),
        (186, "10-09", 7, 9, "Apotheken Ring Ost", 800, "reefer", "normal", 20, 13)],
}
_FLEET_MAINT = {
    "NORTH_A": [(501, 3, "10-09", 7, 10, "inspection")],
    "NORTH_B": [(502, 6, "10-12", 6, 9, "service")],
    "NORTH_C": [],
    "SOUTH_A": [(503, 11, "10-09", 13, 17, "inspection")],
    "SOUTH_B": [],
    "EAST_A": [(504, 14, "10-12", 13, 15, "inspection"), (505, 16, "10-14", 8, 11, "service")],
}


def _fleet(north="A", south="A", east="A"):
    vehicles = {}
    for n, typ, cap, depot, odo, last, status in [
        (1, "van", 1200, "NORTH", 41000, 35000, "active"), (2, "van", 1400, "NORTH", 62300, 50100, "active"),
        (3, "box_truck", 3500, "NORTH", 88000, 80500, "active"), (4, "box_truck", 5000, "NORTH", 120400, 111000, "active"),
        (5, "reefer", 3000, "NORTH", 73900, 66000, "active"), (6, "reefer", 4500, "NORTH", 51200, 44800, "active"),
        (7, "flatbed", 8000, "NORTH", 140000, 124000, "active"),
        (8, "van", 1000, "SOUTH", 95000, 88000, "active"), (9, "van", 1500, "SOUTH", 33300, 25000, "active"),
        (10, "box_truck", 4000, "SOUTH", 71000, 60200, "active"), (11, "reefer", 2500, "SOUTH", 58800, 49900, "active"),
        (12, "flatbed", 9000, "SOUTH", 101000, 93400, "active"),
        (13, "van", 1300, "EAST", 48200, 33000, "active"), (14, "box_truck", 3800, "EAST", 91500, 76100, "active"),
        (15, "box_truck", 4200, "EAST", 60000, 45000, "active"), (16, "reefer", 3200, "EAST", 120300, 103800, "active"),
        (17, "van", 1100, "EAST", 30100, 12000, "out_of_service"), (18, "flatbed", 7500, "EAST", 77700, 61900, "active"),
        (19, "reefer", 3000, "EAST", 22400, 7500, "active"), (20, "reefer", 2800, "EAST", 54000, 39500, "active"),
    ]:
        vehicles["V-%02d" % n] = {"type": typ, "capacity_kg": cap, "depot": depot, "status": status,
                                  "odometer_km": odo, "last_service_km": last}
    drivers = {}
    for n, name, lic, depot, certs, status in [
        (1, "Anja Petersen", "C", "NORTH", ["cold_chain"], "active"), (2, "Bram de Vries", "B", "NORTH", [], "active"),
        (3, "Cem Yildiz", "CE", "NORTH", ["hazmat"], "active"),
        (4, "Dana Kowalczyk", "C", "NORTH", ["cold_chain", "hazmat"], "active"),
        (5, "Emil Strand", "C", "NORTH", [], "active"),
        (6, "Farah Naseri", "CE", "SOUTH", ["cold_chain"], "active"), (7, "Goran Ilic", "B", "SOUTH", [], "active"),
        (8, "Hanne Vos", "C", "SOUTH", ["hazmat"], "active"), (9, "Ivo Marek", "C", "SOUTH", ["cold_chain"], "active"),
        (10, "Jana Novak", "C", "EAST", ["cold_chain"], "active"), (11, "Kai Lindgren", "CE", "EAST", ["hazmat"], "active"),
        (12, "Lotte Brandt", "B", "EAST", [], "active"), (13, "Milan Horvat", "C", "EAST", ["cold_chain"], "active"),
        (14, "Nora Aalto", "C", "EAST", ["cold_chain"], "on_leave"), (15, "Anja Pedersen", "B", "EAST", [], "active"),
    ]:
        drivers["D-%02d" % n] = {"name": name, "licence": lic, "depot": depot, "certs": certs, "status": status}
    jobs, maint = {}, {}
    for depot, key in (("NORTH", north), ("SOUTH", south), ("EAST", east)):
        for row in _FLEET_JOBS["%s_%s" % (depot, key)]:
            n, date, start, end, cust, load, req, prio, v, d = row[:10]
            status = row[10] if len(row) > 10 else ("assigned" if v else "unassigned")
            jobs["J-%d" % n] = {"date": "2026-" + date, "start": start, "end": end, "depot": depot, "customer": cust,
                                "load_kg": load, "requires": req, "priority": prio, "status": status,
                                "vehicle": "V-%02d" % v if v else None, "driver": "D-%02d" % d if d else None}
        for n, v, date, start, end, kind in _FLEET_MAINT["%s_%s" % (depot, key)]:
            maint["M-%d" % n] = {"vehicle": "V-%02d" % v, "date": "2026-" + date, "start": start, "end": end, "kind": kind}
    st = {"today": "2026-10-08", "policy": {"max_daily_hours": 9, "service_interval_km": 15000},
          "depots": ["NORTH", "SOUTH", "EAST"], "vehicles": vehicles, "drivers": drivers, "jobs": jobs,
          "maintenance": maint, "next_job": 200, "next_maint": 520}
    # sanity: every existing assignment is one the env itself would accept (the service-due rule only
    # applies to new assignments, so it is switched off for this replay)
    sim = copy.deepcopy(st)
    sim["policy"]["service_interval_km"] = 10 ** 9
    todo = []
    for k, j in sorted(sim["jobs"].items()):
        if j["status"] == "assigned":
            todo.append((k, j["vehicle"], j["driver"]))
            j["status"], j["vehicle"], j["driver"] = "unassigned", None, None
        elif j["status"] != "done":
            assert j["vehicle"] is None and j["driver"] is None, k
    env = FleetEnv(sim)
    for k, v, d in todo:
        res = env.call("assign_job", {"job_id": k, "vehicle_id": v, "driver_id": d})
        assert "error" not in res, (k, res)
    return st


def _assignments(init, job_ids):
    """All complete (vehicle, driver) assignments of the given unassigned jobs that the env accepts."""
    sols = []

    def rec(env, n, acc):
        if n == len(job_ids):
            sols.append(tuple(acc))
            return
        for v in sorted(env.state["vehicles"]):
            for d in sorted(env.state["drivers"]):
                e2 = FleetEnv(env.state)
                if "error" not in e2.call("assign_job", {"job_id": job_ids[n], "vehicle_id": v, "driver_id": d}):
                    rec(e2, n + 1, acc + [(v, d)])
    rec(FleetEnv(init), 0, [])
    return sols


def _jobs(upd):
    out = {}
    for k, ch in upd.items():
        ch = dict(ch)
        if ch.get("vehicle", 1) is None:
            ch.update({"driver": None, "status": "unassigned"})
        out[k] = ch
    return out


_add("T19", "fleet", _fleet(north="A"),
     "Box truck V-04 at NORTH has broken down. Each job assigned to V-04 that is dated today or tomorrow has to "
     "move to another active NORTH vehicle and keep its driver and its time. Take those jobs in order of date and "
     "start hour, and give each one the vehicle with the smallest capacity that the dispatch policy allows for "
     "that job with that driver and that is free at that time. Jobs on V-04 dated later than tomorrow are just "
     "unassigned and left for the planners. Finished or cancelled jobs are history. When V-04 has no assigned "
     "jobs left, set it out of service and book a 'repair' maintenance window for it tomorrow from 08:00 for 4 "
     "hours. Don't change any other vehicle's existing jobs.",
     [["get_dispatch_info", {}], ["get_vehicle", {"vehicle_id": "V-04"}], ["list_vehicles", {"depot": "NORTH"}],
      ["unassign_job", {"job_id": "J-101"}],
      ["assign_job", {"job_id": "J-101", "vehicle_id": "V-05", "driver_id": "D-05"}],
      ["assign_job", {"job_id": "J-101", "vehicle_id": "V-03", "driver_id": "D-05"}],
      ["unassign_job", {"job_id": "J-102"}],
      ["assign_job", {"job_id": "J-102", "vehicle_id": "V-03", "driver_id": "D-05"}],
      ["assign_job", {"job_id": "J-102", "vehicle_id": "V-06", "driver_id": "D-05"}],
      ["unassign_job", {"job_id": "J-103"}],
      ["assign_job", {"job_id": "J-103", "vehicle_id": "V-05", "driver_id": "D-04"}],
      ["unassign_job", {"job_id": "J-104"}],
      ["set_vehicle_status", {"vehicle_id": "V-04", "status": "out_of_service"}],
      ["schedule_maintenance", {"vehicle_id": "V-04", "date": "2026-10-09", "start_hour": 8, "duration_hours": 4,
                                "kind": "repair"}]],
     [["unassign_job", {"job_id": "J-101"}],
      ["assign_job", {"job_id": "J-101", "vehicle_id": "V-03", "driver_id": "D-05"}],
      ["unassign_job", {"job_id": "J-102"}],
      ["assign_job", {"job_id": "J-102", "vehicle_id": "V-06", "driver_id": "D-05"}],
      ["unassign_job", {"job_id": "J-103"}],
      ["assign_job", {"job_id": "J-103", "vehicle_id": "V-03", "driver_id": "D-04"}],
      ["unassign_job", {"job_id": "J-104"}],
      ["set_vehicle_status", {"vehicle_id": "V-04", "status": "out_of_service"}],
      ["schedule_maintenance", {"vehicle_id": "V-04", "date": "2026-10-09", "start_hour": 8, "duration_hours": 4,
                                "kind": "repair"}]],
     lambda s, i: _final(s, i, changes={
         "jobs": _jobs({"J-101": {"vehicle": "V-03"}, "J-102": {"vehicle": "V-06"}, "J-103": {"vehicle": "V-05"},
                        "J-104": {"vehicle": None}}),
         "vehicles": {"V-04": {"status": "out_of_service"}}},
         new={"maintenance": [{"vehicle": "V-04", "date": "2026-10-09", "start": 8, "end": 12, "kind": "repair"}]}),
     ref_errors=[4, 7], mentions=["V-04", "NORTH"])


def _c20(s, i):
    due = sorted(k for k, v in i["vehicles"].items()
                 if v["depot"] == "EAST" and v["status"] == "active"
                 and v["odometer_km"] - v["last_service_km"] >= i["policy"]["service_interval_km"]
                 and not [1 for m in i["maintenance"].values() if m["vehicle"] == k and m["kind"] == "service"])
    want = []
    for k in due:
        clash = [1 for j in i["jobs"].values() if j["vehicle"] == k and j["status"] == "assigned"
                 and j["date"] == "2026-10-12" and j["start"] < 11 and 8 < j["end"]]
        want.append({"vehicle": k, "date": "2026-10-13" if clash else "2026-10-12", "start": 8, "end": 11,
                     "kind": "service"})
    return due == ["V-13", "V-14", "V-15", "V-18"] and [w["date"][-2:] for w in want] == ["12", "12", "12", "13"] \
        and _final(s, i, new={"maintenance": want})


_add("T20", "fleet", _fleet(),
     "Service round for the EAST depot. Take the service interval from the dispatch policy and work out which "
     "EAST vehicles are due for service. Every due vehicle that is active and does not already have a 'service' "
     "window booked gets one: 3 hours, kind 'service', on Monday 12 October 2026 starting at 08:00. If that slot "
     "collides with something already planned for that vehicle, book the same hours on Tuesday 13 October "
     "instead. Vehicles that are out of service are the workshop's business, skip them, and vehicles of other "
     "depots are not part of this round. Do not move, unassign or cancel any job, and leave existing maintenance "
     "bookings alone.",
     [["get_dispatch_info", {}], ["list_vehicles", {"depot": "EAST"}], ["get_vehicle", {"vehicle_id": "V-13"}],
      ["get_vehicle", {"vehicle_id": "V-14"}], ["get_vehicle", {"vehicle_id": "V-15"}],
      ["get_vehicle", {"vehicle_id": "V-16"}], ["get_vehicle", {"vehicle_id": "V-18"}],
      ["schedule_maintenance", {"vehicle_id": "V-13", "date": "2026-10-12", "start_hour": 8, "duration_hours": 3, "kind": "service"}],
      ["schedule_maintenance", {"vehicle_id": "V-14", "date": "2026-10-12", "start_hour": 8, "duration_hours": 3, "kind": "service"}],
      ["schedule_maintenance", {"vehicle_id": "V-15", "date": "2026-10-12", "start_hour": 8, "duration_hours": 3, "kind": "service"}],
      ["schedule_maintenance", {"vehicle_id": "V-18", "date": "2026-10-12", "start_hour": 8, "duration_hours": 3, "kind": "service"}],
      ["schedule_maintenance", {"vehicle_id": "V-18", "date": "2026-10-13", "start_hour": 8, "duration_hours": 3, "kind": "service"}]],
     [["schedule_maintenance", {"vehicle_id": "V-13", "date": "2026-10-12", "start_hour": 8, "duration_hours": 3, "kind": "service"}],
      ["schedule_maintenance", {"vehicle_id": "V-14", "date": "2026-10-12", "start_hour": 8, "duration_hours": 3, "kind": "service"}],
      ["schedule_maintenance", {"vehicle_id": "V-18", "date": "2026-10-13", "start_hour": 8, "duration_hours": 3, "kind": "service"}]],
     _c20, ref_errors=[10], mentions=["EAST"])

_T21 = _fleet(south="A")
assert _assignments(_T21, ["J-120", "J-121", "J-122", "J-123"]) == [
    (("V-11", "D-09"), ("V-12", "D-06"), ("V-10", "D-08"), ("V-09", "D-08"))]

_add("T21", "fleet", _T21,
     "Tomorrow, 9 October 2026, the SOUTH depot still has four unassigned jobs. All four must be covered, using "
     "only SOUTH's own vehicles and drivers and obeying every rule of the dispatch policy (vehicle type and "
     "capacity, licences, certificates, overlaps, maintenance windows, daily driver hours). You may not change, "
     "move or unassign any job that is already assigned, and you may not touch maintenance bookings or job "
     "times. With the vehicles and drivers that are free tomorrow there is exactly one way to cover all four "
     "jobs: work it out and make the four assignments. Cancelling or rescheduling any of the four is not an "
     "acceptable outcome.",
     [["get_dispatch_info", {}], ["list_jobs", {"date": "2026-10-09", "depot": "SOUTH"}],
      ["list_jobs", {"date": "2026-10-09", "depot": "SOUTH", "page": 2}], ["list_vehicles", {"depot": "SOUTH"}],
      ["list_drivers", {"depot": "SOUTH"}], ["get_vehicle", {"vehicle_id": "V-11"}],
      ["assign_job", {"job_id": "J-121", "vehicle_id": "V-12", "driver_id": "D-06"}],
      ["assign_job", {"job_id": "J-120", "vehicle_id": "V-11", "driver_id": "D-09"}],
      ["assign_job", {"job_id": "J-122", "vehicle_id": "V-10", "driver_id": "D-08"}],
      ["assign_job", {"job_id": "J-123", "vehicle_id": "V-09", "driver_id": "D-08"}]],
     [["assign_job", {"job_id": "J-120", "vehicle_id": "V-11", "driver_id": "D-06"}],
      ["assign_job", {"job_id": "J-122", "vehicle_id": "V-10", "driver_id": "D-08"}],
      ["assign_job", {"job_id": "J-123", "vehicle_id": "V-09", "driver_id": "D-08"}]],
     lambda s, i: _final(s, i, changes={"jobs": {
         "J-120": {"status": "assigned", "vehicle": "V-11", "driver": "D-09"},
         "J-121": {"status": "assigned", "vehicle": "V-12", "driver": "D-06"},
         "J-122": {"status": "assigned", "vehicle": "V-10", "driver": "D-08"},
         "J-123": {"status": "assigned", "vehicle": "V-09", "driver": "D-08"}}}),
     mentions=["SOUTH"])

_add("T22", "fleet", _fleet(north="B"),
     "Norlund Foods has asked us to move all of their deliveries planned for Friday 9 October 2026 to Monday "
     "12 October, at the same hours. Move every Norlund Foods job that is on that Friday and has not been "
     "cancelled. A job that had a vehicle and driver should get exactly the same vehicle and driver back on "
     "Monday if the system accepts that pairing at the new time; if it does not, leave that job unassigned on "
     "Monday for the dispatcher - do not substitute another vehicle or driver. A job that was unassigned stays "
     "unassigned. Norlund Marine is a different customer and is not affected, and Norlund Foods jobs on other "
     "days stay where they are.",
     [["get_dispatch_info", {}], ["list_jobs", {"date": "2026-10-09", "depot": "NORTH"}],
      ["list_jobs", {"date": "2026-10-09", "depot": "NORTH", "page": 2}],
      ["unassign_job", {"job_id": "J-130"}], ["reschedule_job", {"job_id": "J-130", "date": "2026-10-12", "start_hour": 7}],
      ["assign_job", {"job_id": "J-130", "vehicle_id": "V-06", "driver_id": "D-01"}],
      ["unassign_job", {"job_id": "J-131"}], ["reschedule_job", {"job_id": "J-131", "date": "2026-10-12", "start_hour": 11}],
      ["assign_job", {"job_id": "J-131", "vehicle_id": "V-01", "driver_id": "D-02"}],
      ["unassign_job", {"job_id": "J-132"}], ["reschedule_job", {"job_id": "J-132", "date": "2026-10-12", "start_hour": 14}],
      ["assign_job", {"job_id": "J-132", "vehicle_id": "V-05", "driver_id": "D-04"}],
      ["reschedule_job", {"job_id": "J-133", "date": "2026-10-12", "start_hour": 9}]],
     [["unassign_job", {"job_id": "J-130"}], ["reschedule_job", {"job_id": "J-130", "date": "2026-10-12", "start_hour": 7}],
      ["unassign_job", {"job_id": "J-131"}], ["reschedule_job", {"job_id": "J-131", "date": "2026-10-12", "start_hour": 11}],
      ["assign_job", {"job_id": "J-131", "vehicle_id": "V-01", "driver_id": "D-02"}],
      ["unassign_job", {"job_id": "J-132"}], ["reschedule_job", {"job_id": "J-132", "date": "2026-10-12", "start_hour": 14}],
      ["assign_job", {"job_id": "J-132", "vehicle_id": "V-05", "driver_id": "D-01"}],
      ["reschedule_job", {"job_id": "J-133", "date": "2026-10-12", "start_hour": 9}]],
     lambda s, i: _final(s, i, changes={"jobs": _jobs({
         "J-130": {"date": "2026-10-12", "vehicle": None}, "J-131": {"date": "2026-10-12"},
         "J-132": {"date": "2026-10-12", "vehicle": None}, "J-133": {"date": "2026-10-12"}})}),
     ref_errors=[5, 11], mentions=["Norlund Foods", "Norlund Marine"])

_add("T23", "fleet", _fleet(),
     "Baltic Pharma needs an urgent refrigerated run from the EAST depot tomorrow, 9 October 2026, from 10:00 to "
     "13:00, 2,400 kg. Create that job with priority urgent and get it assigned. Check first which EAST reefers "
     "are allowed to take new work at all under the dispatch policy. None of the usable ones is free in that "
     "slot, so bump the lowest-priority job that occupies a usable reefer during the slot: move that job to "
     "Monday 12 October at the same hours and give it back the same vehicle and driver there. Then put the new "
     "Baltic Pharma job on the vehicle you freed, with the driver of the job you bumped. Every other job stays "
     "exactly as it is.",
     [["get_dispatch_info", {}], ["list_vehicles", {"depot": "EAST", "type": "reefer"}],
      ["list_jobs", {"date": "2026-10-09", "depot": "EAST"}], ["list_drivers", {"depot": "EAST"}],
      ["create_job", {"date": "2026-10-09", "start_hour": 10, "end_hour": 13, "depot": "EAST",
                      "customer": "Baltic Pharma", "load_kg": 2400, "requires": "reefer", "priority": "urgent"}],
      ["assign_job", {"job_id": "J-200", "vehicle_id": "V-16", "driver_id": "D-13"}],
      ["unassign_job", {"job_id": "J-150"}],
      ["reschedule_job", {"job_id": "J-150", "date": "2026-10-12", "start_hour": 9}],
      ["assign_job", {"job_id": "J-150", "vehicle_id": "V-20", "driver_id": "D-13"}],
      ["assign_job", {"job_id": "J-200", "vehicle_id": "V-20", "driver_id": "D-13"}]],
     [["create_job", {"date": "2026-10-09", "start_hour": 10, "end_hour": 13, "depot": "EAST",
                      "customer": "Baltic Pharma", "load_kg": 2400, "requires": "reefer", "priority": "urgent"}],
      ["unassign_job", {"job_id": "J-151"}],
      ["reschedule_job", {"job_id": "J-151", "date": "2026-10-12", "start_hour": 10}],
      ["assign_job", {"job_id": "J-151", "vehicle_id": "V-19", "driver_id": "D-10"}],
      ["assign_job", {"job_id": "J-200", "vehicle_id": "V-19", "driver_id": "D-10"}]],
     lambda s, i: _final(s, i, changes={"jobs": {"J-150": {"date": "2026-10-12"}}},
                         new={"jobs": [{"date": "2026-10-09", "start": 10, "end": 13, "depot": "EAST",
                                        "customer": lambda v: isinstance(v, str), "load_kg": 2400,
                                        "requires": "reefer", "priority": "urgent", "status": "assigned",
                                        "vehicle": "V-20", "driver": "D-13"}]}),
     ref_errors=[5], mentions=["EAST"], creates=["Baltic Pharma"])

_add("T24", "fleet", _fleet(north="C"),
     "Anja Petersen at NORTH (not Anja Pedersen) is off sick tomorrow, 9 October 2026. Every job she has "
     "tomorrow keeps its vehicle and its time but needs another active NORTH driver who may do it under the "
     "dispatch policy: right licence for that vehicle, required certificates, free at that time, and within the "
     "daily hours limit. Take her jobs in order of start hour. For each one choose, among the drivers who are "
     "eligible for it, the one with the fewest job hours tomorrow at that moment - counting the jobs you have "
     "already handed over in this round - and on a tie the lower driver id. Her jobs on other days stay with "
     "her, and nobody else's jobs change.",
     [["list_drivers", {"depot": "NORTH"}], ["get_driver", {"driver_id": "D-01"}], ["get_dispatch_info", {}],
      ["get_driver", {"driver_id": "D-02"}], ["get_driver", {"driver_id": "D-03"}],
      ["get_driver", {"driver_id": "D-04"}], ["get_driver", {"driver_id": "D-05"}],
      ["unassign_job", {"job_id": "J-160"}],
      ["assign_job", {"job_id": "J-160", "vehicle_id": "V-05", "driver_id": "D-04"}],
      ["unassign_job", {"job_id": "J-161"}],
      ["assign_job", {"job_id": "J-161", "vehicle_id": "V-03", "driver_id": "D-05"}],
      ["unassign_job", {"job_id": "J-162"}],
      ["assign_job", {"job_id": "J-162", "vehicle_id": "V-01", "driver_id": "D-04"}]],
     [["unassign_job", {"job_id": "J-160"}],
      ["assign_job", {"job_id": "J-160", "vehicle_id": "V-05", "driver_id": "D-04"}],
      ["unassign_job", {"job_id": "J-161"}],
      ["assign_job", {"job_id": "J-161", "vehicle_id": "V-03", "driver_id": "D-04"}],
      ["unassign_job", {"job_id": "J-162"}],
      ["assign_job", {"job_id": "J-162", "vehicle_id": "V-01", "driver_id": "D-03"}]],
     lambda s, i: _final(s, i, changes={"jobs": {
         "J-160": {"driver": "D-04"}, "J-161": {"driver": "D-05"}, "J-162": {"driver": "D-04"}}}),
     mentions=["Anja Petersen", "Anja Pedersen", "NORTH"])


# --------------------------------------------------------------------------
# hotel fixture + tasks T25-T30
# --------------------------------------------------------------------------
def _hotel(rows):
    """rows: (id, guest, room, check_in 'MM-DD', check_out 'MM-DD', guests, status, extras, paid)
    paid may be "full" (= the computed total). The total is always priced with the env's own rule."""
    rooms = {}
    for num, typ, feats in [
        (101, "standard", ["accessible"]), (102, "standard", []), (103, "standard", []), (104, "deluxe", []),
        (105, "deluxe", ["accessible"]), (106, "family", []),
        (201, "standard", []), (202, "standard", ["balcony"]), (203, "deluxe", ["sea_view"]),
        (204, "deluxe", ["sea_view"]), (205, "deluxe", []), (206, "family", []),
        (301, "standard", ["sea_view"]), (302, "standard", []), (303, "deluxe", ["sea_view", "balcony"]),
        (304, "deluxe", ["sea_view"]), (305, "suite", ["sea_view"]), (306, "family", ["sea_view"]),
        (401, "deluxe", ["sea_view", "balcony"]), (402, "suite", ["sea_view", "balcony"]), (403, "suite", []),
        (404, "standard", []), (405, "deluxe", []), (406, "family", []),
    ]:
        rooms[str(num)] = {"type": typ, "floor": num // 100, "features": feats, "status": "ok"}
    guests = {}
    for n, name, tier in [
        (1, "Henrik Aaltonen", "gold"), (2, "Henrik Altonen", "none"), (3, "Ingrid Solberg", "none"),
        (4, "Paolo Ricci", "none"), (5, "Marguerite Dufour", "platinum"), (6, "Kenji Watanabe", "platinum"),
        (7, "Sofia Marchetti", "platinum"), (8, "Tobias Reinhardt", "gold"), (9, "Amelie Durand", "platinum"),
        (10, "Viktor Sokolov", "none"), (11, "Leila Haddad", "gold"), (12, "Oskar Lindberg", "none"),
        (13, "Priya Nair", "platinum"), (14, "Callum Fraser", "none"), (15, "Hana Kobayashi", "gold"),
        (16, "Mateo Alvarez", "none"), (17, "Freya Jorgensen", "platinum"), (18, "Dmitri Petrov", "none"),
        (19, "Henrik Aaltonen", "none"),
    ]:
        guests["G-%02d" % n] = {"name": name, "tier": tier}
    st = {"today": "2026-10-08",
          "policy": {"weekend_surcharge": 30, "discount_pct": {"none": 0, "gold": 10, "platinum": 20},
                     "extras": {"breakfast": 15, "parking": 10}, "free_cancel_days": 3},
          "room_types": {"standard": {"rate": 100, "max_guests": 2}, "deluxe": {"rate": 150, "max_guests": 3},
                         "family": {"rate": 180, "max_guests": 5}, "suite": {"rate": 240, "max_guests": 4}},
          "rooms": rooms, "guests": guests, "reservations": {}, "next_res": 900}
    for rid, g, room, ci, co, n, status, extras, paid in rows:
        r = {"guest": "G-%02d" % g, "room": str(room), "rate_type": rooms[str(room)]["type"],
             "check_in": "2026-" + ci, "check_out": "2026-" + co, "guests": n, "status": status,
             "extras": sorted(extras), "total": 0, "paid": 0, "fee": 0}
        r["total"] = _h_total(st, r)
        r["paid"] = r["total"] if paid == "full" else paid
        assert n <= st["room_types"][r["rate_type"]]["max_guests"], rid
        st["reservations"]["R-%d" % rid] = r
    env = HotelEnv(st)
    for k, r in st["reservations"].items():   # sanity: no double bookings in the fixture
        assert r["status"] not in _ACTIVE or env._blocker(r["room"], r["check_in"], r["check_out"], skip=k) is None, k
    return st


_add("T25", "hotel", _hotel([
    (701, 10, 304, "10-06", "10-10", 2, "checked_in", [], "full"),
    (702, 12, 304, "10-12", "10-15", 2, "booked", [], 150),
    (703, 14, 304, "10-20", "10-22", 2, "booked", ["breakfast"], 0),
    (704, 16, 304, "10-16", "10-18", 2, "cancelled", [], 0),
    (705, 18, 304, "10-01", "10-05", 1, "checked_out", [], "full"),
    (706, 8, 203, "10-05", "10-09", 2, "checked_in", [], "full"),
    (707, 11, 204, "10-08", "10-11", 2, "booked", [], 0),
    (708, 15, 303, "10-10", "10-13", 2, "booked", [], 0),
    (709, 2, 203, "10-11", "10-13", 1, "booked", [], 0),
    (710, 4, 203, "10-19", "10-23", 2, "booked", [], 0),
    (711, 3, 204, "10-21", "10-24", 2, "booked", [], 0),
    (712, 6, 303, "10-18", "10-21", 2, "booked", [], 0),
    (713, 7, 401, "10-20", "10-25", 2, "booked", [], 0),
    (714, 9, 305, "10-19", "10-21", 2, "booked", [], 0)]),
     "Room 304 has a water leak and has to go into maintenance right away. Before that, every active reservation "
     "in room 304 - the guest staying there now and the ones booked for later - must be moved, with unchanged "
     "dates. Move each to another room of the same type that also has a sea view and is free for that stay (for "
     "the guest who is in house: free from today until departure); if there are several, take the lowest room "
     "number. If no such room is free for a reservation, upgrade that reservation to a suite with sea view, "
     "again the lowest free room number, but the guest must keep paying the rate they pay now. Cancelled and "
     "past reservations don't matter. Then put room 304 into maintenance.",
     [["get_hotel_info", {}], ["list_reservations", {"room_id": "304"}],
      ["set_room_status", {"room_id": "304", "status": "maintenance"}],
      ["search_availability", {"check_in": "2026-10-08", "check_out": "2026-10-10", "room_type": "deluxe", "feature": "sea_view"}],
      ["modify_reservation", {"reservation_id": "R-701", "room_id": "303"}],
      ["search_availability", {"check_in": "2026-10-12", "check_out": "2026-10-15", "room_type": "deluxe", "feature": "sea_view"}],
      ["modify_reservation", {"reservation_id": "R-702", "room_id": "204"}],
      ["search_availability", {"check_in": "2026-10-20", "check_out": "2026-10-22", "room_type": "deluxe", "feature": "sea_view"}],
      ["search_availability", {"check_in": "2026-10-20", "check_out": "2026-10-22", "room_type": "suite", "feature": "sea_view"}],
      ["modify_reservation", {"reservation_id": "R-703", "room_id": "402", "keep_rate": True}],
      ["set_room_status", {"room_id": "304", "status": "maintenance"}]],
     [["modify_reservation", {"reservation_id": "R-701", "room_id": "303"}],
      ["modify_reservation", {"reservation_id": "R-702", "room_id": "204"}],
      ["modify_reservation", {"reservation_id": "R-703", "room_id": "402"}],
      ["set_room_status", {"room_id": "304", "status": "maintenance"}]],
     lambda s, i: _final(s, i, changes={
         "reservations": {"R-701": {"room": "303"}, "R-702": {"room": "204"}, "R-703": {"room": "402"}},
         "rooms": {"304": {"status": "maintenance"}}}),
     ref_errors=[2], mentions=["304"])

_add("T26", "hotel", _hotel([
    (720, 1, 205, "10-09", "10-11", 2, "booked", [], "full"),
    (721, 1, 102, "10-10", "10-12", 1, "booked", [], 50),
    (722, 1, 305, "10-11", "10-14", 2, "booked", [], 200),
    (723, 19, 104, "11-20", "11-23", 2, "booked", [], 0),
    (724, 1, 201, "10-07", "10-09", 1, "checked_in", [], "full"),
    (725, 1, 302, "09-10", "09-12", 1, "checked_out", [], "full"),
    (726, 1, 405, "10-25", "10-27", 2, "cancelled", [], 0),
    (727, 2, 202, "10-10", "10-12", 1, "booked", [], 100),
    (728, 19, 103, "10-09", "10-10", 1, "booked", [], "full"),
    (729, 19, 301, "09-20", "09-22", 1, "checked_out", [], "full")]),
     "Henrik Aaltonen has to cancel every stay of his that has not started yet. Careful: he is in our system "
     "twice under exactly that name (a duplicate guest profile) and the stays under both profiles are his, "
     "while Henrik Altonen is a different person whose bookings must not be touched. Cancel each of those "
     "upcoming reservations; the system sets the cancellation fee according to policy. Then, for each one you "
     "cancelled, refund whatever he paid on it beyond its fee. Where he paid less than the fee, refund nothing "
     "and charge nothing - accounts will follow up. The stay he is in at the moment continues unchanged.",
     [["find_guests", {"query": "Henrik"}], ["list_reservations", {"guest_id": "G-01"}],
      ["list_reservations", {"guest_id": "G-19"}], ["get_hotel_info", {}],
      ["cancel_reservation", {"reservation_id": "R-720"}], ["refund", {"reservation_id": "R-720", "amount": 162}],
      ["cancel_reservation", {"reservation_id": "R-721"}], ["cancel_reservation", {"reservation_id": "R-722"}],
      ["refund", {"reservation_id": "R-722", "amount": 200}], ["cancel_reservation", {"reservation_id": "R-723"}],
      ["cancel_reservation", {"reservation_id": "R-728"}]],
     [["cancel_reservation", {"reservation_id": "R-720"}], ["refund", {"reservation_id": "R-720", "amount": 162}],
      ["cancel_reservation", {"reservation_id": "R-721"}], ["cancel_reservation", {"reservation_id": "R-722"}],
      ["refund", {"reservation_id": "R-722", "amount": 200}]],
     lambda s, i: _final(s, i, changes={"reservations": {
         "R-720": {"status": "cancelled", "fee": 162, "paid": 162},
         "R-721": {"status": "cancelled", "fee": 117, "paid": 50},
         "R-722": {"status": "cancelled", "fee": 0, "paid": 0},
         "R-723": {"status": "cancelled", "fee": 0, "paid": 0},
         "R-728": {"status": "cancelled", "fee": 130, "paid": 130}}}),
     mentions=["Henrik Aaltonen", "Henrik Altonen"])

_add("T27", "hotel", _hotel([
    (730, 3, 202, "10-06", "10-09", 1, "checked_in", [], "full"),
    (731, 4, 202, "10-09", "10-12", 2, "booked", [], 100),
    (732, 10, 101, "10-08", "10-10", 1, "booked", [], 0),
    (733, 12, 102, "10-10", "10-13", 2, "booked", [], 0),
    (734, 14, 201, "10-12", "10-14", 1, "booked", [], 0),
    (735, 16, 103, "10-02", "10-05", 2, "checked_out", [], "full"),
    (736, 18, 203, "10-07", "10-11", 2, "checked_in", ["breakfast"], 300),
    (737, 3, 404, "11-14", "11-16", 1, "booked", [], 0)]),
     "Ingrid Solberg, who is staying in room 202, would like to stay two more nights. If room 202 is already "
     "booked for those nights, first move the incoming reservation to another room of the same type that is free "
     "for its whole stay: preferably one with a balcony, and if there is none, any room of that type; in either "
     "case the lowest room number. The incoming guest's dates and payments must not change. Then extend Ingrid's "
     "current stay by the two nights, add breakfast to it, and charge her card for everything that is then "
     "outstanding on that reservation, so that its balance is exactly zero. Her other booking later in the year "
     "is not affected.",
     [["find_guests", {"query": "Solberg"}], ["list_reservations", {"guest_id": "G-03"}],
      ["modify_reservation", {"reservation_id": "R-730", "check_out": "2026-10-11"}],
      ["list_reservations", {"room_id": "202"}],
      ["search_availability", {"check_in": "2026-10-09", "check_out": "2026-10-12", "room_type": "standard", "feature": "balcony"}],
      ["search_availability", {"check_in": "2026-10-09", "check_out": "2026-10-12", "room_type": "standard"}],
      ["modify_reservation", {"reservation_id": "R-731", "room_id": "103"}],
      ["modify_reservation", {"reservation_id": "R-730", "check_out": "2026-10-11"}],
      ["set_extra", {"reservation_id": "R-730", "extra": "breakfast", "enabled": True}],
      ["get_reservation", {"reservation_id": "R-730"}],
      ["record_payment", {"reservation_id": "R-730", "amount": 335}]],
     [["modify_reservation", {"reservation_id": "R-731", "room_id": "103"}],
      ["modify_reservation", {"reservation_id": "R-730", "check_out": "2026-10-11"}],
      ["record_payment", {"reservation_id": "R-730", "amount": 260}]],
     lambda s, i: _final(s, i, changes={"reservations": {
         "R-731": {"room": "103"},
         "R-730": {"check_out": "2026-10-11", "extras": ["breakfast"], "total": 635, "paid": 635}}}),
     ref_errors=[2], mentions=["Ingrid Solberg", "202"])

_add("T28", "hotel", _hotel([
    (740, 10, 101, "10-05", "10-08", 1, "checked_in", [], "full"),
    (741, 8, 203, "10-04", "10-08", 2, "checked_in", ["parking"], 300),
    (742, 12, 106, "10-06", "10-08", 4, "checked_in", [], 400),
    (743, 14, 402, "10-02", "10-08", 2, "checked_in", ["breakfast"], 900),
    (749, 13, 305, "10-05", "10-08", 2, "checked_in", [], 76),
    (745, 18, 201, "10-06", "10-09", 1, "checked_in", [], 230),
    (746, 3, 404, "10-08", "10-10", 1, "booked", [], 0),
    (747, 4, 103, "10-03", "10-08", 2, "checked_out", [], "full"),
    (748, 6, 205, "10-07", "10-11", 2, "checked_in", [], 100),
    (750, 9, 401, "10-07", "10-12", 2, "checked_in", [], 0),
    (751, 11, 204, "10-06", "10-10", 2, "checked_in", ["breakfast"], 700)]),
     "Morning check-outs. For every guest who is in house and due to leave today, settle the bill and check them "
     "out: if there is a balance due, charge their card for exactly that balance; if they have paid too much, "
     "refund the excess; then check them out. One exception: if the balance due is more than 500, do not charge "
     "and do not check out - the front-office manager wants to speak to that guest first, so leave that "
     "reservation completely untouched. A balance of exactly 500 is still charged normally. Guests leaving on "
     "other days, today's arrivals and guests who have already checked out are not part of this.",
     [["get_hotel_info", {}], ["list_reservations", {"date": "2026-10-08", "status": "checked_in"}],
      ["list_reservations", {"date": "2026-10-08", "status": "checked_in", "page": 2}],
      ["get_reservation", {"reservation_id": "R-740"}], ["get_reservation", {"reservation_id": "R-741"}],
      ["get_reservation", {"reservation_id": "R-742"}], ["get_reservation", {"reservation_id": "R-743"}],
      ["get_reservation", {"reservation_id": "R-749"}], ["check_out", {"reservation_id": "R-740"}],
      ["record_payment", {"reservation_id": "R-741", "amount": 280}], ["check_out", {"reservation_id": "R-741"}],
      ["refund", {"reservation_id": "R-742", "amount": 40}], ["check_out", {"reservation_id": "R-742"}],
      ["record_payment", {"reservation_id": "R-749", "amount": 500}], ["check_out", {"reservation_id": "R-749"}]],
     [["check_out", {"reservation_id": "R-740"}],
      ["record_payment", {"reservation_id": "R-741", "amount": 280}], ["check_out", {"reservation_id": "R-741"}],
      ["refund", {"reservation_id": "R-742", "amount": 40}], ["check_out", {"reservation_id": "R-742"}],
      ["record_payment", {"reservation_id": "R-749", "amount": 500}], ["check_out", {"reservation_id": "R-749"}],
      ["record_payment", {"reservation_id": "R-743", "amount": 690}], ["check_out", {"reservation_id": "R-743"}]],
     lambda s, i: i["reservations"]["R-743"]["total"] == 1590 and _final(s, i, changes={"reservations": {
         "R-740": {"status": "checked_out"},
         "R-741": {"status": "checked_out", "paid": 580},
         "R-742": {"status": "checked_out", "paid": 360},
         "R-749": {"status": "checked_out", "paid": 576}}}),
     mentions=[])   # the prompt names no entity: the guests are found by date and status

_add("T29", "hotel", _hotel([
    (760, 6, 102, "10-09", "10-11", 2, "booked", [], 0),
    (761, 7, 201, "10-09", "10-14", 1, "booked", [], 0),
    (762, 8, 302, "10-09", "10-11", 2, "booked", [], 0),
    (763, 9, 205, "10-09", "10-12", 2, "booked", [], 0),
    (764, 13, 404, "10-09", "10-10", 1, "booked", ["breakfast"], 0),
    (765, 17, 103, "10-10", "10-12", 2, "booked", [], 0),
    (766, 5, 106, "10-09", "10-11", 4, "booked", [], 0),
    (767, 10, 104, "10-10", "10-12", 2, "booked", [], 0),
    (768, 12, 105, "10-12", "10-15", 2, "booked", [], 0),
    (769, 14, 203, "10-07", "10-10", 2, "checked_in", [], 0),
    (770, 16, 204, "10-08", "10-13", 2, "booked", [], 0),
    (771, 18, 303, "10-06", "10-12", 2, "checked_in", [], 0),
    (772, 3, 304, "10-09", "10-16", 2, "booked", [], 0),
    (773, 4, 401, "10-05", "10-15", 2, "checked_in", [], 0),
    (774, 11, 405, "10-13", "10-15", 2, "booked", [], 0),
    (775, 15, 301, "10-08", "10-10", 1, "booked", [], 0)]),
     "Loyalty upgrades for tomorrow's arrivals (check-in on 9 October 2026). Every platinum member arriving "
     "tomorrow whose reservation is for a standard room gets a complimentary upgrade to a deluxe room, provided "
     "a deluxe room is free for their entire stay: give them the lowest-numbered deluxe room that is free for "
     "all their nights, and they keep paying the rate they pay now. Work through the reservations in order of "
     "reservation id; a room you have just given to one guest is of course no longer free for the next. If no "
     "deluxe room is free for someone's whole stay, leave that reservation as it is. Gold members get nothing, "
     "neither do guests who already booked a better room type, and arrivals on other days are not included.",
     [["get_hotel_info", {}], ["list_reservations", {"date": "2026-10-09", "status": "booked"}],
      ["list_reservations", {"date": "2026-10-09", "status": "booked", "page": 2}],
      ["find_guests", {"tier": "platinum"}],
      ["search_availability", {"check_in": "2026-10-09", "check_out": "2026-10-11", "room_type": "deluxe"}],
      ["modify_reservation", {"reservation_id": "R-760", "room_id": "105", "keep_rate": True}],
      ["search_availability", {"check_in": "2026-10-09", "check_out": "2026-10-14", "room_type": "deluxe"}],
      ["search_availability", {"check_in": "2026-10-09", "check_out": "2026-10-10", "room_type": "deluxe"}],
      ["modify_reservation", {"reservation_id": "R-764", "room_id": "104", "keep_rate": True}]],
     [["modify_reservation", {"reservation_id": "R-760", "room_id": "105"}],
      ["modify_reservation", {"reservation_id": "R-764", "room_id": "104"}]],
     lambda s, i: _final(s, i, changes={"reservations": {"R-760": {"room": "105"}, "R-764": {"room": "104"}}}),
     mentions=["platinum"])

_add("T30", "hotel", _hotel([
    (780, 5, 206, "10-16", "10-19", 4, "booked", [], "full"),
    (781, 5, 204, "10-16", "10-19", 2, "booked", [], 200),
    (782, 10, 204, "11-01", "11-04", 2, "booked", [], 0),
    (783, 12, 203, "11-03", "11-06", 2, "booked", [], 0),
    (784, 14, 206, "10-28", "11-02", 3, "booked", [], 0),
    (785, 5, 402, "12-20", "12-23", 2, "booked", [], 0),
    (786, 16, 303, "10-31", "11-03", 2, "booked", [], 0),
    (787, 18, 304, "11-04", "11-07", 2, "booked", [], 0),
    (788, 5, 105, "09-01", "09-03", 1, "checked_out", [], "full")]),
     "Marguerite Dufour is moving her family trip: both of her reservations for 16 to 19 October 2026 move to "
     "2 to 5 November 2026. Each reservation stays in its current room if that room is free for the new dates; "
     "if it is not, move it to another room of the same type that has a sea view, lowest room number. The system "
     "re-prices automatically. Afterwards, if the new totals of the two reservations together come to less than "
     "800, add parking to the family-room reservation (only that one). Finally, for each of the two "
     "reservations: if she has paid more than its new total, refund the difference; if she has paid less, leave "
     "the balance open. Her December booking is not affected.",
     [["find_guests", {"query": "Dufour"}], ["list_reservations", {"guest_id": "G-05"}], ["get_hotel_info", {}],
      ["modify_reservation", {"reservation_id": "R-780", "check_in": "2026-11-02", "check_out": "2026-11-05"}],
      ["modify_reservation", {"reservation_id": "R-781", "check_in": "2026-11-02", "check_out": "2026-11-05"}],
      ["search_availability", {"check_in": "2026-11-02", "check_out": "2026-11-05", "room_type": "deluxe", "feature": "sea_view"}],
      ["modify_reservation", {"reservation_id": "R-781", "room_id": "401", "check_in": "2026-11-02", "check_out": "2026-11-05"}],
      ["set_extra", {"reservation_id": "R-780", "extra": "parking", "enabled": True}],
      ["get_reservation", {"reservation_id": "R-780"}], ["refund", {"reservation_id": "R-780", "amount": 18}]],
     [["modify_reservation", {"reservation_id": "R-780", "check_in": "2026-11-02", "check_out": "2026-11-05"}],
      ["modify_reservation", {"reservation_id": "R-781", "room_id": "401", "check_in": "2026-11-02", "check_out": "2026-11-05"}],
      ["refund", {"reservation_id": "R-780", "amount": 48}]],
     lambda s, i: _final(s, i, changes={"reservations": {
         "R-780": {"check_in": "2026-11-02", "check_out": "2026-11-05", "extras": ["parking"], "total": 462, "paid": 462},
         "R-781": {"room": "401", "check_in": "2026-11-02", "check_out": "2026-11-05", "total": 360}}}),
     ref_errors=[4], mentions=["Marguerite Dufour"])


def _free(st, ci, co, **kw):
    args = {"check_in": "2026-" + ci, "check_out": "2026-" + co}
    args.update(kw)
    return [r["room_id"] for r in HotelEnv(st).call("search_availability", args)["available_rooms"]]


def _hotel_oracles():
    """Independent re-derivation of the 'lowest free room' choices the hotel checks rely on."""
    t = dict((x["id"], x["init"]) for x in TASKS)
    i = t["T25"]
    assert _free(i, "10-08", "10-10", room_type="deluxe", feature="sea_view")[0] == "303"
    assert _free(i, "10-12", "10-15", room_type="deluxe", feature="sea_view")[0] == "204"
    assert _free(i, "10-20", "10-22", room_type="deluxe", feature="sea_view") == []
    assert _free(i, "10-20", "10-22", room_type="suite", feature="sea_view")[0] == "402"
    i = t["T27"]
    assert _free(i, "10-09", "10-12", room_type="standard", feature="balcony") == []
    assert _free(i, "10-09", "10-12", room_type="standard")[0] == "103"
    i = t["T29"]
    plat = [k for k, r in sorted(i["reservations"].items())
            if r["check_in"] == "2026-10-09" and r["status"] == "booked" and r["rate_type"] == "standard"
            and i["guests"][r["guest"]]["tier"] == "platinum"]
    assert plat == ["R-760", "R-761", "R-764"], plat
    env, got = HotelEnv(i), {}
    for k in plat:
        r = env.state["reservations"][k]
        free = env.call("search_availability", {"check_in": r["check_in"], "check_out": r["check_out"],
                                                "room_type": "deluxe"})["available_rooms"]
        if free:
            got[k] = free[0]["room_id"]
            env.call("modify_reservation", {"reservation_id": k, "room_id": got[k], "keep_rate": True})
    assert got == {"R-760": "105", "R-764": "104"}, got
    i = t["T30"]
    assert "204" not in _free(i, "11-02", "11-05") and "206" in _free(i, "11-02", "11-05")
    assert _free(i, "11-02", "11-05", room_type="deluxe", feature="sea_view")[0] == "401"


_hotel_oracles()


def _fleet_oracles():
    """Independent re-derivation of the rule-based choices in T19 (smallest vehicle) and T24 (fewest hours)."""
    t = dict((x["id"], x["init"]) for x in TASKS)
    env, got = FleetEnv(t["T19"]), {}
    mine = sorted((j["date"], j["start"], k) for k, j in t["T19"]["jobs"].items()
                  if j["vehicle"] == "V-04" and j["status"] == "assigned" and j["date"] <= "2026-10-09")
    for _, _, k in mine:
        d = env.state["jobs"][k]["driver"]
        env.call("unassign_job", {"job_id": k})
        for cap, v in sorted((x["capacity_kg"], v) for v, x in env.state["vehicles"].items()
                             if x["depot"] == "NORTH" and v != "V-04"):
            if "error" not in env.call("assign_job", {"job_id": k, "vehicle_id": v, "driver_id": d}):
                got[k] = v
                break
    assert got == {"J-101": "V-03", "J-102": "V-06", "J-103": "V-05"}, got
    env, got = FleetEnv(t["T24"]), {}
    mine = sorted((j["start"], k) for k, j in t["T24"]["jobs"].items()
                  if j["driver"] == "D-01" and j["status"] == "assigned" and j["date"] == "2026-10-09")
    for _, k in mine:
        v = env.state["jobs"][k]["vehicle"]
        env.call("unassign_job", {"job_id": k})
        cands = []
        for d, x in sorted(env.state["drivers"].items()):
            if x["depot"] != "NORTH" or d == "D-01":
                continue
            probe = FleetEnv(env.state)
            if "error" not in probe.call("assign_job", {"job_id": k, "vehicle_id": v, "driver_id": d}):
                hours = sum(j["end"] - j["start"] for j in env.state["jobs"].values()
                            if j["driver"] == d and j["status"] == "assigned" and j["date"] == "2026-10-09")
                cands.append((hours, d))
        got[k] = min(cands)[1]
        env.call("assign_job", {"job_id": k, "vehicle_id": v, "driver_id": got[k]})
    assert got == {"J-160": "D-04", "J-161": "D-05", "J-162": "D-04"}, got


_fleet_oracles()


# --------------------------------------------------------------------------
# calibration tasks TP1-TP6 (same style and difficulty as the test tasks)
# --------------------------------------------------------------------------
_add("TP1", "bank", _bank(),
     "Bruno Keller's monthly split. Find his most recent salary deposit from Kettler AG on his 'Salary account' "
     "(salary only - other deposits don't count). Move 30% of that salary to his 'House deposit' account and "
     "20% of it to his 'Emergency pot'. However, the Emergency pot must not end up above 3,000: whatever part of "
     "the 20% does not fit under that cap goes to House deposit as well. In addition, his pending scheduled "
     "payment to Kettler Pension Plan should from now on be 5% of that salary: replace it with a payment of the "
     "new amount, same account, same payee and same date. His other scheduled payments must not change.",
     [["find_customers", {"query": "Keller"}], ["list_accounts", {"customer_id": "C-110"}],
      ["list_transactions", {"account_id": "A-2060", "type": "deposit"}], ["get_account", {"account_id": "A-2062"}],
      ["list_scheduled", {"account_id": "A-2060", "status": "pending"}],
      ["transfer", {"from_account": "A-2060", "to_account": "A-2061", "amount": 1800}],
      ["transfer", {"from_account": "A-2060", "to_account": "A-2062", "amount": 550}],
      ["cancel_scheduled", {"scheduled_id": "S-430"}],
      ["schedule_payment", {"from_account": "A-2060", "payee_id": "P-08", "amount": 235, "date": "2026-10-28"}]],
     [["transfer", {"from_account": "A-2060", "to_account": "A-2061", "amount": 1410}],
      ["transfer", {"from_account": "A-2060", "to_account": "A-2062", "amount": 940}],
      ["cancel_scheduled", {"scheduled_id": "S-430"}],
      ["schedule_payment", {"from_account": "A-2060", "payee_id": "P-08", "amount": 235, "date": "2026-10-28"}]],
     lambda s, i: _final(s, i, changes={
         "accounts": _bal(i, {"A-2060": -2350, "A-2061": 1800, "A-2062": 550}),
         "scheduled": {"S-430": {"status": "cancelled"}}},
         new={"scheduled": [{"from": "A-2060", "payee": "P-08", "amount": 235, "date": "2026-10-28",
                             "status": "pending"}]}),
     mentions=["Bruno Keller", "Kettler AG", "Salary account", "House deposit", "Emergency pot", "Kettler Pension Plan"])


def _pTP2(st):
    st["environments"]["dev"]["deployed"]["reports"] = "2.3.1"
    st["environments"]["dev"]["previous"]["reports"] = ["2.2.0", "2.3.0"]
    st["environments"]["staging"]["deployed"]["reports"] = "2.2.0"
    st["environments"]["staging"]["previous"]["reports"] = []
    for b in ("B-104", "B-113", "B-153", "B-172", "B-173"):
        st["builds"][b]["quarantined"] = True


_add("TP2", "deploy", _pipe(_pTP2),
     "Several builds were quarantined this morning, and the dev environment must not keep running quarantined "
     "builds. For every service whose current dev version is a quarantined build, roll dev back one step at a "
     "time until that service is on a build that is not quarantined. If a rollback is refused because another "
     "service on dev needs the newer version, roll that other service back one step first, even though its own "
     "build is fine. Do not deploy anything, do not touch staging or production, and do not change quarantine "
     "flags or approvals. Services on dev that are not affected stay as they are.",
     [["get_pipeline_info", {}], ["get_environment", {"env": "dev"}], ["list_builds", {"quarantined": True}],
      ["rollback", {"service": "auth", "env": "dev"}], ["get_service", {"service": "auth"}],
      ["rollback", {"service": "notify", "env": "dev"}], ["rollback", {"service": "auth", "env": "dev"}],
      ["rollback", {"service": "catalog-ui", "env": "dev"}], ["rollback", {"service": "reports", "env": "dev"}],
      ["get_environment", {"env": "dev"}], ["rollback", {"service": "reports", "env": "dev"}]],
     [["rollback", {"service": "notify", "env": "dev"}], ["rollback", {"service": "auth", "env": "dev"}],
      ["rollback", {"service": "catalog-ui", "env": "dev"}], ["rollback", {"service": "reports", "env": "dev"}]],
     lambda s, i: _final(s, i, changes={"environments": _envs(i, {"dev": {
         "auth": ["5.1.2", "5.1.3"], "notify": ["0.9.4", "0.9.5"], "catalog-ui": ["4.2.0", "4.3.0"],
         "reports": ["2.2.0"]}})}),
     ref_errors=[3], mentions=["dev"])

_add("TP3", "registrar", _reg(),
     "Kofi Mensah and Lena Fischer want to trade places in MATH220: Kofi goes into Lena's section and Lena into "
     "Kofi's. Both sections are full, and when you are finished each of the two sections must have the same "
     "capacity and the same waitlist as now - nobody from a waitlist gets in through this. Lena has said that "
     "if her new MATH220 section clashes with her drawing class, her drawing class should be moved to its other "
     "section, and if that is not possible she would rather drop drawing than miss the trade. Kofi has no such "
     "problem. Apart from that, nobody's enrolments may change.",
     [["find_students", {"query": "Mensah"}], ["find_students", {"query": "Fischer"}],
      ["get_student", {"student_id": "S-19"}], ["get_student", {"student_id": "S-17"}],
      ["get_section", {"section_id": "MATH220-A"}], ["get_section", {"section_id": "MATH220-B"}],
      ["swap_section", {"student_id": "S-19", "from_section": "MATH220-A", "to_section": "MATH220-B"}],
      ["drop", {"student_id": "S-19", "section_id": "MATH220-A"}],
      ["swap_section", {"student_id": "S-17", "from_section": "MATH220-B", "to_section": "MATH220-A"}],
      ["list_sections", {"course_id": "ART150"}],
      ["swap_section", {"student_id": "S-17", "from_section": "ART150-B", "to_section": "ART150-A"}],
      ["drop", {"student_id": "S-17", "section_id": "ART150-B"}],
      ["swap_section", {"student_id": "S-17", "from_section": "MATH220-B", "to_section": "MATH220-A"}],
      ["enroll", {"student_id": "S-19", "section_id": "MATH220-B"}]],
     [["set_capacity", {"section_id": "MATH220-B", "capacity": 5}],
      ["swap_section", {"student_id": "S-19", "from_section": "MATH220-A", "to_section": "MATH220-B"}],
      ["drop", {"student_id": "S-17", "section_id": "ART150-B"}],
      ["swap_section", {"student_id": "S-17", "from_section": "MATH220-B", "to_section": "MATH220-A"}]],
     lambda s, i: _final(s, i, changes=_sec(i, {
         "MATH220-A": {"rem": ["S-19"], "add": ["S-17"]}, "MATH220-B": {"rem": ["S-17"], "add": ["S-19"]},
         "ART150-B": {"rem": ["S-17"]}})),
     ref_errors=[6, 8, 10], mentions=["Kofi Mensah", "Lena Fischer", "MATH220"])

_add("TP4", "fleet", _fleet(south="B"),
     "Van V-08 at SOUTH is being decommissioned from Monday 12 October 2026. Every job assigned to V-08 that is "
     "dated 12 October or later has to move off it, keeping its driver and its time: first choice is van V-09; "
     "if the system does not accept V-09 for a job, try box truck V-10 with the same driver; and if that is not "
     "accepted either, leave the job unassigned. Jobs before 12 October stay on V-08. When that is done, book a "
     "'decommission' maintenance window for V-08 on 12 October from 06:00 for 12 hours. Do not change the jobs "
     "that V-09 and V-10 already have, and do not set V-08 out of service yet.",
     [["get_dispatch_info", {}], ["get_vehicle", {"vehicle_id": "V-08"}],
      ["unassign_job", {"job_id": "J-171"}], ["assign_job", {"job_id": "J-171", "vehicle_id": "V-09", "driver_id": "D-07"}],
      ["unassign_job", {"job_id": "J-172"}], ["assign_job", {"job_id": "J-172", "vehicle_id": "V-09", "driver_id": "D-07"}],
      ["assign_job", {"job_id": "J-172", "vehicle_id": "V-10", "driver_id": "D-07"}],
      ["unassign_job", {"job_id": "J-173"}], ["assign_job", {"job_id": "J-173", "vehicle_id": "V-09", "driver_id": "D-08"}],
      ["unassign_job", {"job_id": "J-178"}], ["assign_job", {"job_id": "J-178", "vehicle_id": "V-09", "driver_id": "D-08"}],
      ["assign_job", {"job_id": "J-178", "vehicle_id": "V-10", "driver_id": "D-08"}],
      ["unassign_job", {"job_id": "J-174"}], ["assign_job", {"job_id": "J-174", "vehicle_id": "V-09", "driver_id": "D-07"}],
      ["schedule_maintenance", {"vehicle_id": "V-08", "date": "2026-10-12", "start_hour": 6, "duration_hours": 12,
                                "kind": "decommission"}]],
     [["unassign_job", {"job_id": "J-171"}], ["assign_job", {"job_id": "J-171", "vehicle_id": "V-09", "driver_id": "D-07"}],
      ["unassign_job", {"job_id": "J-172"}],
      ["schedule_maintenance", {"vehicle_id": "V-08", "date": "2026-10-12", "start_hour": 6, "duration_hours": 12,
                                "kind": "decommission"}]],
     lambda s, i: _final(s, i, changes={"jobs": _jobs({
         "J-171": {"vehicle": "V-09"}, "J-172": {"vehicle": None}, "J-173": {"vehicle": "V-09"},
         "J-178": {"vehicle": "V-10"}, "J-174": {"vehicle": "V-09"}})},
         new={"maintenance": [{"vehicle": "V-08", "date": "2026-10-12", "start": 6, "end": 18, "kind": "decommission"}]}),
     ref_errors=[5, 6, 10], mentions=["V-08", "V-09", "V-10", "SOUTH"])

_add("TP5", "hotel", _hotel([
    (790, 10, 102, "10-07", "10-09", 1, "booked", [], 0),
    (791, 8, 203, "10-07", "10-10", 2, "booked", [], "full"),
    (792, 6, 305, "10-07", "10-10", 2, "booked", [], "full"),
    (793, 13, 404, "10-07", "10-08", 1, "booked", [], "full"),
    (794, 12, 101, "10-07", "10-09", 1, "checked_in", [], 100),
    (795, 14, 201, "10-08", "10-10", 1, "booked", [], 0),
    (796, 16, 301, "10-07", "10-09", 1, "cancelled", [], 0),
    (797, 7, 401, "10-06", "10-09", 2, "checked_in", [], "full"),
    (798, 9, 205, "10-08", "10-11", 2, "booked", [], "full")]),
     "Night audit, no-shows. Every reservation whose check-in date was yesterday and whose status is still "
     "'booked' is a no-show. The standard treatment is: cancel it (the system applies the fee from the policy) "
     "and refund whatever the guest paid beyond that fee. Platinum members get a courtesy instead: do not cancel, "
     "move their check-in date to today, keep the check-out date, and refund whatever they have then overpaid. "
     "If that is not possible for a platinum member because no night would be left, treat that reservation like "
     "everyone else's. Do not touch guests who did arrive, today's arrivals or reservations that are already "
     "cancelled.",
     [["get_hotel_info", {}], ["list_reservations", {"date": "2026-10-07", "status": "booked"}],
      ["find_guests", {"tier": "platinum"}], ["cancel_reservation", {"reservation_id": "R-790"}],
      ["cancel_reservation", {"reservation_id": "R-791"}], ["refund", {"reservation_id": "R-791", "amount": 297}],
      ["modify_reservation", {"reservation_id": "R-792", "check_in": "2026-10-08"}],
      ["refund", {"reservation_id": "R-792", "amount": 192}],
      ["modify_reservation", {"reservation_id": "R-793", "check_in": "2026-10-08"}],
      ["cancel_reservation", {"reservation_id": "R-793"}]],
     [["cancel_reservation", {"reservation_id": "R-790"}],
      ["cancel_reservation", {"reservation_id": "R-791"}], ["refund", {"reservation_id": "R-791", "amount": 297}],
      ["cancel_reservation", {"reservation_id": "R-792"}], ["refund", {"reservation_id": "R-792", "amount": 408}],
      ["cancel_reservation", {"reservation_id": "R-793"}]],
     lambda s, i: _final(s, i, changes={"reservations": {
         "R-790": {"status": "cancelled", "fee": 100},
         "R-791": {"status": "cancelled", "fee": 135, "paid": 135},
         "R-792": {"check_in": "2026-10-08", "total": 408, "paid": 408},
         "R-793": {"status": "cancelled", "fee": 80, "paid": 80}}}),
     ref_errors=[8], mentions=["platinum"])

_add("TP6", "bank", _bank(),
     "Tax provision for Sable & Finch Studio. Add up the customer deposits (transactions of type deposit) that "
     "arrived on their 'Operating' account during September 2026 - transfers from their own accounts are not "
     "customer deposits - and set aside 25% of that sum as a new earmark hold on their 'Tax reserve' account, "
     "expiring on 2026-12-31. The old earmark hold on Tax reserve has run past its expiry date: release it "
     "first. If Tax reserve then still does not have enough available funds for the new hold, move exactly the "
     "missing amount over from Operating, no more, and then place the hold. Their savings account is not "
     "involved.",
     [["find_customers", {"query": "Sable"}], ["list_accounts", {"customer_id": "C-111"}], ["get_bank_info", {}],
      ["list_transactions", {"account_id": "A-2070", "type": "deposit"}],
      ["list_holds", {"account_id": "A-2071", "status": "active"}], ["release_hold", {"hold_id": "H-340"}],
      ["get_account", {"account_id": "A-2071"}],
      ["transfer", {"from_account": "A-2070", "to_account": "A-2071", "amount": 200}],
      ["place_hold", {"account_id": "A-2071", "amount": 2100, "reason": "earmark", "expires": "2026-12-31"}]],
     [["release_hold", {"hold_id": "H-340"}],
      ["transfer", {"from_account": "A-2070", "to_account": "A-2071", "amount": 1325}],
      ["place_hold", {"account_id": "A-2071", "amount": 3225, "reason": "earmark", "expires": "2026-12-31"}]],
     lambda s, i: sum(x["amount"] for x in i["transactions"].values()
                      if x["account"] == "A-2070" and x["type"] == "deposit" and x["date"][:7] == "2026-09") == 8400
     and _final(s, i, changes={
         "accounts": _bal(i, {"A-2070": -200, "A-2071": 200}), "holds": {"H-340": {"status": "released"}}},
         new={"holds": [{"account": "A-2071", "amount": 2100, "reason": "earmark", "expires": "2026-12-31",
                         "status": "active"}]}),
     mentions=["Sable & Finch Studio", "Operating", "Tax reserve"])


# Which difficulty ingredients each task combines (documentation; _verify insists on at least three):
#   a  multi-way conditional decided by data that must be read and aggregated
#   b  business-rule error on the natural first attempt that needs a specific recovery
#   c  ordering dependency (the env rejects, or the outcome changes, in the wrong order)
#   d  batch over several entities picked by a compound criterion, with look-alikes that must stay untouched
#   e  computed argument that depends on two or more earlier read results
#   f  rule that is only stated by a policy read-tool / tool result, not by the prompt
#   g  explicit "nothing else may change" with a tempting side effect
_FEATURES = {
    "T01": "bcdfg", "T02": "adefg", "T03": "abdef", "T04": "adeg", "T05": "bcdef", "T06": "ade",
    "T07": "bcfg", "T08": "bcfg", "T09": "bcdf", "T10": "acdfg", "T11": "bcdf", "T12": "adfg",
    "T13": "abce", "T14": "bdf", "T15": "abce", "T16": "abdfg", "T17": "bcd", "T18": "abce",
    "T19": "abcf", "T20": "abdf", "T21": "afg", "T22": "bcd", "T23": "abcf", "T24": "acef",
    "T25": "abcd", "T26": "adef", "T27": "bce", "T28": "acde", "T29": "acdg", "T30": "abe",
    "TP1": "ade", "TP2": "bcd", "TP3": "bcg", "TP4": "bcd", "TP5": "adef", "TP6": "acde",
}
for _t in TASKS:
    _t["features"] = _FEATURES[_t["id"]]


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


_GARBAGE = [None, "", "zzz", "/", "A-2001; drop", -1, 0, 3, 10 ** 12, 1.5, 2.0, float("inf"), float("nan"), True, False,
            [], [None], [{}], ["a", 1], [[1]], {}, {"x": {"y": [1]}}, {"id": 1, "qty": "2"},
            "2026-13-45", "25:99", "2026-10-08", "2026-10-09", "2026-10-12", "09:00", "9:00", "é中", "null"]


def _safe_call(env, name, args, label):
    before = _clone(env.state)
    try:
        res = env.call(name, args)
    except Exception as e:  # pragma: no cover - this is what the fuzz is for
        raise AssertionError("%s: call raised %r for %r %r" % (label, e, name, args))
    json.dumps(res)
    if _is_err(res):
        assert env.state == before, "%s: state changed on error for %r %r" % (label, name, args)
    if _is_read(name):
        assert env.state == before, "%s: read tool %r changed the state" % (label, name)
    json.dumps(env.state)
    return res


def _fuzz():
    rng = random.Random(20261008)
    calls = 0
    for ename in sorted(ENVS):
        cls = ENVS[ename]
        inits = [t["init"] for t in TASKS if t["env"] == ename]
        pool = set()
        for ini in inits:
            _strings(ini, pool)
        pool = sorted(pool)
        names = [t["function"]["name"] for t in cls.TOOLS]
        env = cls(inits[0])
        for name in names + [None, 5, "nope", "", [], {}, 1.5, "transfer; drop"]:
            for args in _GARBAGE + ["{}", 7]:
                _safe_call(env, name, args, ename)
                calls += 1

        def rand_value(schema, depth=0):
            r = rng.random()
            if r < 0.25 or depth > 3:
                return rng.choice(_GARBAGE)
            t = schema.get("type")
            if t == "string":
                if "enum" in schema and rng.random() < 0.85:
                    return rng.choice(schema["enum"])
                return rng.choice(pool)
            if t == "integer":
                return rng.choice([-5, 0, 1, 2, 3, 6, 8, 9, 10, 12, 14, 25, 100, 370, 1000, 5000, 9999])
            if t == "boolean":
                return rng.random() < 0.5
            if t == "array":
                return [rand_value(schema["items"], depth + 1) for _ in range(rng.randint(0, 3))]
            if t == "object":
                out = {}
                for k, sub in schema.get("properties", {}).items():
                    if k in schema.get("required", []) or rng.random() < 0.5:
                        out[k] = rand_value(sub, depth + 1)
                if rng.random() < 0.05:
                    out["bogus"] = 1
                return out
            return None

        def typed_value(key, schema):
            """A plausible value for a parameter: ids of the right family, so that many calls succeed."""
            if "enum" in schema:
                return rng.choice(schema["enum"])
            t = schema.get("type")
            if t == "boolean":
                return rng.random() < 0.5
            if t == "integer":
                return rng.choice([1, 2, 3, 5, 8, 9, 10, 12, 50, 200, 1000])
            if "date" in key or key in ("check_in", "check_out", "expires"):
                return "2026-10-%02d" % rng.randint(8, 20)
            return rng.choice(pool)

        ok_writes = 0
        for n in range(3000):
            if n % 150 == 0:
                env = cls(rng.choice(inits))
            tool = rng.choice(cls.TOOLS)["function"]
            if n % 2:
                args = rand_value(tool["parameters"])
            else:
                props = tool["parameters"]["properties"]
                args = dict((k, typed_value(k, sub)) for k, sub in props.items()
                            if k in tool["parameters"]["required"] or rng.random() < 0.3)
            res = _safe_call(env, tool["name"], args, ename)
            if not _is_err(res) and not _is_read(tool["name"]):
                ok_writes += 1
            calls += 1
        assert ok_writes > 0, (ename, "random fuzz never produced a successful write")
    # mutate every argument of every reference call with every garbage value
    for t in TASKS:
        base = ENVS[t["env"]](t["init"])          # state just before each reference step
        for step, (name, args) in enumerate(t["reference"]):
            for key in list(args) + ["__extra__"]:
                for g in _GARBAGE:
                    env = ENVS[t["env"]](base.state)
                    bad = copy.deepcopy(args)
                    bad[key] = g
                    _safe_call(env, name, bad, t["id"])
                    calls += 1
            for key in args:
                env = ENVS[t["env"]](base.state)
                bad = copy.deepcopy(args)
                del bad[key]
                _safe_call(env, name, bad, t["id"])
                calls += 1
            base.call(name, copy.deepcopy(args))
    return calls


def _schema_ok(schema, path):
    """No union types, no null, only simple types; arrays of scalars and flat objects only."""
    t = schema.get("type")
    assert isinstance(t, str), (path, "type must be a single string, got %r" % (t,))
    assert t in ("string", "integer", "boolean", "array", "object"), (path, t)
    for bad in ("anyOf", "oneOf", "allOf", "nullable"):
        assert bad not in schema, (path, bad)
    if "enum" in schema:
        assert all(isinstance(x, str) and x for x in schema["enum"]), (path, "enum")
    if t == "array":
        assert schema["items"]["type"] in ("string", "integer", "boolean"), (path, "array items must be scalars")
    if t == "object":
        for k, sub in schema.get("properties", {}).items():
            _schema_ok(sub, path + "." + k)


def _no_empty(obj, where):
    if obj is None or obj == "":
        raise AssertionError("%s: reference passes None or an empty string" % (where,))
    if isinstance(obj, dict):
        for v in obj.values():
            _no_empty(v, where)
    elif isinstance(obj, list):
        for v in obj:
            _no_empty(v, where)


_ID_PATTERNS = [r"\b[A-Z]{1,5}\d{0,3}-[A-Z0-9]{1,5}\b",     # C-101, B-123, MATH220-A, LAB-1, AUD-A
                r"\b[A-Z]{2,5}\d{3}\b",                     # course ids
                r"\b\d+\.\d+\.\d+\b",                       # versions
                r"\b[A-Z]{4,}\b"]                           # depots etc. written in capitals


def _prompt_entities(t):
    """Every id-like token, quoted name, room number and declared mention in the prompt must exist in init."""
    pool = set()
    _strings(t["init"], pool)
    blob = "\n".join(sorted(pool))
    vocab = set()                      # enum values of the env's tool schemas may be quoted too ('repair', ...)
    _strings(ENVS[t["env"]].TOOLS, vocab)
    prompt = t["prompt"]
    found = set()
    for pat in _ID_PATTERNS:
        for tok in re.findall(pat, prompt):
            found.add(tok)
            assert tok in pool or tok in t["creates"], (t["id"], "prompt names %r which is not in init" % tok)
    for tok in re.findall(r"(?<![A-Za-z0-9])'([^']{2,40})'(?![A-Za-z0-9])", prompt):
        found.add(tok)
        assert tok in pool or tok in vocab or tok in t["creates"], (t["id"], "prompt quotes %r which is not in init" % tok)
    for tok in re.findall(r"[Rr]ooms? (\d{3})\b", prompt):
        found.add(tok)
        assert tok in t["init"].get("rooms", {}), (t["id"], "prompt names room %r which is not in init" % tok)
    for m in t["mentions"]:
        assert m in prompt, (t["id"], "declared mention %r is not in the prompt" % m)
        assert m in blob, (t["id"], "prompt mentions %r which is not in init" % m)
    return len(found) + len(t["mentions"])


def _alt_orders(t, rng, tries=300):
    """Replay the reference's successful WRITE calls in other orders. An order is 'valid' if no call errors;
    every valid order must satisfy check. Orders that break a declared seq group are not tried."""
    writes = [n for n, (name, _) in enumerate(t["reference"]) if not _is_read(name) and n not in t["ref_errors"]]
    orders, seen = [list(reversed(writes))], set()
    for _ in range(tries):
        p = list(writes)
        rng.shuffle(p)
        orders.append(p)
    # also: every adjacent swap of the reference order
    for n in range(len(writes) - 1):
        p = list(writes)
        p[n], p[n + 1] = p[n + 1], p[n]
        orders.append(p)
    valid = 0
    for p in orders:
        if tuple(p) in seen or p == writes:
            continue
        seen.add(tuple(p))
        if any([x for x in p if x in g] != [x for x in writes if x in g] for g in t["seq"]):
            continue
        env = ENVS[t["env"]](t["init"])
        ok = True
        for n in p:
            name, args = t["reference"][n]
            if _is_err(env.call(name, copy.deepcopy(args))):
                ok = False
                break
        if not ok:
            continue
        valid += 1
        assert t["check"](env.state) is True, (t["id"], "valid alternative write order fails check", p)
    return valid, len(writes)


# Hand-written alternative ROUTES (different calls, not just a different order) that are equally valid
# solutions; each must satisfy check. Guards against checks that only fit the reference's route.
_ALT_ROUTES = {
    "T01": [["transfer", {"from_account": "A-2002", "to_account": "A-2001", "amount": 3875}],
            ["transfer", {"from_account": "A-2002", "to_account": "A-2001", "amount": 3000}],
            ["cancel_scheduled", {"scheduled_id": "S-402"}], ["cancel_scheduled", {"scheduled_id": "S-401"}],
            ["release_hold", {"hold_id": "H-302"}], ["release_hold", {"hold_id": "H-301"}],
            ["transfer", {"from_account": "A-2002", "to_account": "A-2001", "amount": 485}],
            ["close_account", {"account_id": "A-2002"}],
            ["schedule_payment", {"from_account": "A-2001", "payee_id": "P-05", "amount": 450, "date": "2026-11-03"}],
            ["schedule_payment", {"from_account": "A-2001", "payee_id": "P-02", "amount": 300, "date": "2026-10-20"}]],
    "T02": [["transfer", {"from_account": "A-2018", "to_account": "A-2016", "amount": 3300}],
            ["transfer", {"from_account": "A-2010", "to_account": "A-2016", "amount": 3800}],
            ["transfer", {"from_account": "A-2010", "to_account": "A-2016", "amount": 3800}],
            ["transfer", {"from_account": "A-2017", "to_account": "A-2016", "amount": 1000}],
            ["transfer", {"from_account": "A-2017", "to_account": "A-2016", "amount": 450}],
            ["transfer", {"from_account": "A-2011", "to_account": "A-2016", "amount": 2400}]],
    "T05": [["release_hold", {"hold_id": "H-330"}],
            ["transfer", {"from_account": "A-2040", "to_account": "A-2042", "amount": 5000}],
            ["transfer", {"from_account": "A-2041", "to_account": "A-2040", "amount": 1450}],
            ["transfer", {"from_account": "A-2040", "to_account": "A-2042", "amount": 1500}]],
    "T07": [["approve_build", {"build_id": "B-123", "approver_id": "U-02"}],
            ["deploy", {"build_id": "B-112", "env": "staging"}], ["deploy", {"build_id": "B-112", "env": "prod"}],
            ["deploy", {"build_id": "B-123", "env": "staging"}], ["deploy", {"build_id": "B-123", "env": "prod"}]],
    "T09": [["quarantine_build", {"build_id": "B-172"}], ["rollback", {"service": "reports", "env": "staging"}],
            ["quarantine_build", {"build_id": "B-172"}], ["quarantine_build", {"build_id": "B-132"}],
            ["rollback", {"service": "catalog", "env": "staging"}], ["quarantine_build", {"build_id": "B-132"}],
            ["quarantine_build", {"build_id": "B-163"}], ["quarantine_build", {"build_id": "B-153"}],
            ["quarantine_build", {"build_id": "B-104"}]],
    "T13": [["set_capacity", {"section_id": "PHYS210-A", "capacity": 12}],
            ["drop", {"student_id": "S-12", "section_id": "PHYS210-B"}],
            ["drop", {"student_id": "S-03", "section_id": "PHYS210-B"}],
            ["enroll", {"student_id": "S-03", "section_id": "PHYS210-A"}],
            ["drop", {"student_id": "S-09", "section_id": "PHYS210-B"}],
            ["enroll", {"student_id": "S-09", "section_id": "PHYS210-A"}],
            ["drop", {"student_id": "S-18", "section_id": "PHYS210-B"}],
            ["enroll", {"student_id": "S-18", "section_id": "PHYS210-A"}],
            ["drop", {"student_id": "S-15", "section_id": "PHYS210-B"}],
            ["leave_waitlist", {"student_id": "S-21", "section_id": "PHYS210-B"}],
            ["cancel_section", {"section_id": "PHYS210-B"}],
            ["join_waitlist", {"student_id": "S-15", "section_id": "PHYS210-A"}],
            ["join_waitlist", {"student_id": "S-21", "section_id": "PHYS210-A"}]],
    "T18": [["drop", {"student_id": "S-06", "section_id": "STAT230-A"}],
            ["enroll", {"student_id": "S-22", "section_id": "STAT230-A"}],
            ["drop", {"student_id": "S-06", "section_id": "MATH201-B"}],
            ["enroll", {"student_id": "S-06", "section_id": "CHEM110-B"}],
            ["enroll", {"student_id": "S-06", "section_id": "MATH201-A"}]],
    "T19": [["unassign_job", {"job_id": "J-104"}], ["unassign_job", {"job_id": "J-103"}],
            ["unassign_job", {"job_id": "J-102"}], ["unassign_job", {"job_id": "J-101"}],
            ["set_vehicle_status", {"vehicle_id": "V-04", "status": "out_of_service"}],
            ["schedule_maintenance", {"vehicle_id": "V-04", "date": "2026-10-09", "start_hour": 8,
                                      "duration_hours": 4, "kind": "repair"}],
            ["assign_job", {"job_id": "J-103", "vehicle_id": "V-05", "driver_id": "D-04"}],
            ["assign_job", {"job_id": "J-102", "vehicle_id": "V-06", "driver_id": "D-05"}],
            ["assign_job", {"job_id": "J-101", "vehicle_id": "V-03", "driver_id": "D-05"}]],
    "T23": [["unassign_job", {"job_id": "J-150"}],
            ["reschedule_job", {"job_id": "J-150", "date": "2026-10-12", "start_hour": 9}],
            ["assign_job", {"job_id": "J-150", "vehicle_id": "V-20", "driver_id": "D-13"}],
            ["create_job", {"date": "2026-10-09", "start_hour": 10, "end_hour": 13, "depot": "EAST",
                            "customer": "Baltic Pharma GmbH", "load_kg": 2400, "requires": "reefer", "priority": "urgent"}],
            ["assign_job", {"job_id": "J-200", "vehicle_id": "V-20", "driver_id": "D-13"}]],
    "T25": [["modify_reservation", {"reservation_id": "R-703", "room_id": "402", "keep_rate": True,
                                    "check_in": "2026-10-20", "check_out": "2026-10-22"}],
            ["modify_reservation", {"reservation_id": "R-702", "room_id": "204"}],
            ["modify_reservation", {"reservation_id": "R-701", "room_id": "303", "guests": 2}],
            ["set_room_status", {"room_id": "304", "status": "maintenance"}]],
    "T27": [["modify_reservation", {"reservation_id": "R-731", "room_id": "103"}],
            ["set_extra", {"reservation_id": "R-730", "extra": "breakfast", "enabled": True}],
            ["record_payment", {"reservation_id": "R-730", "amount": 45}],
            ["modify_reservation", {"reservation_id": "R-730", "check_out": "2026-10-11"}],
            ["record_payment", {"reservation_id": "R-730", "amount": 290}]],
    "T30": [["modify_reservation", {"reservation_id": "R-781", "room_id": "401"}],
            ["modify_reservation", {"reservation_id": "R-781", "check_in": "2026-11-02", "check_out": "2026-11-05"}],
            ["modify_reservation", {"reservation_id": "R-780", "check_in": "2026-11-02", "check_out": "2026-11-05"}],
            ["set_extra", {"reservation_id": "R-780", "extra": "parking", "enabled": True}],
            ["refund", {"reservation_id": "R-780", "amount": 10}], ["refund", {"reservation_id": "R-780", "amount": 8}]],
    "TP1": [["cancel_scheduled", {"scheduled_id": "S-430"}],
            ["schedule_payment", {"from_account": "A-2060", "payee_id": "P-08", "amount": 235, "date": "2026-10-28"}],
            ["transfer", {"from_account": "A-2060", "to_account": "A-2061", "amount": 1410}],
            ["transfer", {"from_account": "A-2060", "to_account": "A-2062", "amount": 550}],
            ["transfer", {"from_account": "A-2060", "to_account": "A-2061", "amount": 390}]],
    "TP3": [["set_capacity", {"section_id": "MATH220-B", "capacity": 5}],
            ["swap_section", {"student_id": "S-19", "from_section": "MATH220-A", "to_section": "MATH220-B"}],
            ["drop", {"student_id": "S-17", "section_id": "ART150-B"}],
            ["swap_section", {"student_id": "S-17", "from_section": "MATH220-B", "to_section": "MATH220-A"}],
            ["set_capacity", {"section_id": "MATH220-B", "capacity": 4}]],
    "TP5": [["cancel_reservation", {"reservation_id": "R-793"}], ["cancel_reservation", {"reservation_id": "R-791"}],
            ["refund", {"reservation_id": "R-791", "amount": 200}], ["refund", {"reservation_id": "R-791", "amount": 97}],
            ["modify_reservation", {"reservation_id": "R-792", "check_in": "2026-10-08", "check_out": "2026-10-10"}],
            ["refund", {"reservation_id": "R-792", "amount": 192}], ["cancel_reservation", {"reservation_id": "R-790"}]],
}


def _verify(expect_ids=None):
    ids = [t["id"] for t in TASKS]
    if expect_ids is not None:
        assert ids == expect_ids, ids
    assert len(set(ids)) == len(ids)
    for ename, cls in ENVS.items():
        assert 10 <= len(cls.TOOLS) <= 14, (ename, len(cls.TOOLS))
        json.dumps(cls.TOOLS)
        names = [tool["function"]["name"] for tool in cls.TOOLS]
        assert len(set(names)) == len(names)
        for tool in cls.TOOLS:
            fn = tool["function"]
            assert tool["type"] == "function" and fn["parameters"]["type"] == "object"
            assert hasattr(cls, "_t_" + fn["name"]), fn["name"]
            _schema_ok(fn["parameters"], fn["name"])
            for r in fn["parameters"]["required"]:
                assert r in fn["parameters"]["properties"], (fn["name"], r)
    ok = 0
    rng = random.Random(7)
    report = []
    for t in TASKS:
        tid = t["id"]
        cls = ENVS[t["env"]]
        tools = dict((x["function"]["name"], x["function"]) for x in cls.TOOLS)
        words = len(t["prompt"].split())
        assert 60 <= words <= 200, (tid, "prompt words", words)
        assert 9 <= len(t["reference"]) <= 16, (tid, "reference length", len(t["reference"]))
        assert len(set(t["features"])) >= 3 and set(t["features"]) <= set("abcdefg"), (tid, "features")
        json.dumps(t["init"])
        json.dumps(t["reference"])
        json.dumps(t["trap"])
        _no_empty(t["reference"], tid)
        n_ent = _prompt_entities(t)
        # (a) untouched initial state must fail
        env = cls(t["init"])
        assert env.state == t["init"] and env.state is not t["init"]
        assert t["check"](env.state) is False, (tid, "check passes on the initial state")
        # (b) reference solves it; errors only where declared; reads never change the state
        chars = 0
        for n, (name, args) in enumerate(t["reference"]):
            assert name in tools, (tid, "unknown tool in reference", name)
            before = copy.deepcopy(env.state)
            res = env.call(name, copy.deepcopy(args))
            chars += len(json.dumps(res))
            assert _is_err(res) == (n in t["ref_errors"]), (tid, "reference step", n, name, res)
            if _is_read(name) or _is_err(res):
                assert env.state == before, (tid, "state changed by read/error step", n)
            else:
                assert env.state != before, (tid, "reference write changed nothing", n, name)
        assert t["check"](env.state) is True, (tid, "reference does not satisfy check")
        assert chars < 45000, (tid, "reference transcript too long for the context window", chars)
        json.dumps(env.state)
        # every read tool that takes no required arguments must leave a solved state solved
        for fn in tools.values():
            if not fn["parameters"]["required"]:
                assert not _is_err(env.call(fn["name"], {})), (tid, fn["name"])
        assert t["check"](env.state) is True, (tid, "read tools changed the state")
        # (d) trap must change something and fail
        env = cls(t["init"])
        for name, args in t["trap"]:
            assert name in tools, (tid, "unknown tool in trap", name)
            json.dumps(env.call(name, copy.deepcopy(args)))
        assert env.state != t["init"], (tid, "trap changed nothing")
        assert t["check"](env.state) is False, (tid, "trap passes the check")
        # (e) dropping any single successful write from the reference must fail
        writes = [n for n, (name, _) in enumerate(t["reference"]) if not _is_read(name) and n not in t["ref_errors"]]
        for skip in writes:
            env = cls(t["init"])
            for n, (name, args) in enumerate(t["reference"]):
                if n != skip:
                    env.call(name, copy.deepcopy(args))
            assert t["check"](env.state) is False, (tid, "check passes although reference step %d was skipped" % skip)
        # (f) alternative valid write orders must pass
        valid, nw = _alt_orders(t, rng)
        # (g) hand-written alternative routes must pass as well
        if tid in _ALT_ROUTES:
            env = cls(t["init"])
            for name, args in _ALT_ROUTES[tid]:
                env.call(name, copy.deepcopy(args))   # may include a refused attempt, as a model's route would
            assert t["check"](env.state) is True, (tid, "alternative route fails check")
        report.append((tid, len(t["reference"]), nw, valid, words, n_ent, chars))
        # init must not have been mutated by any of the above
        assert t["check"](copy.deepcopy(t["init"])) is False
        ok += 1
    calls = _fuzz()
    for t in TASKS:   # fuzz must not have leaked into the fixtures
        env = ENVS[t["env"]](t["init"])
        for name, args in t["reference"]:
            env.call(name, copy.deepcopy(args))
        assert t["check"](env.state) is True, (t["id"], "fixture mutated by fuzz")
    return ok, calls, report


if __name__ == "__main__":
    _expect = ["T%02d" % n for n in range(1, 31)] + ["TP%d" % n for n in range(1, 7)]
    _ok, _calls, _report = _verify(_expect)
    for _e in sorted(ENVS):
        assert len([t for t in TASKS[:30] if t["env"] == _e]) == 6, _e
        assert len([t for t in TASKS[30:] if t["env"] == _e]) >= 1, _e
    print("envs: " + ", ".join("%s (%d tools)" % (k, len(v.TOOLS)) for k, v in sorted(ENVS.items())))
    print("reference calls per task: min %d, max %d; prompt words: min %d, max %d" % (
        min(r[1] for r in _report), max(r[1] for r in _report), min(r[4] for r in _report), max(r[4] for r in _report)))
    print("alternative write orders: %d valid orders replayed over %d tasks, all pass check; tasks with none: %s" % (
        sum(r[3] for r in _report), len(_report), ", ".join(r[0] for r in _report if r[3] == 0) or "-"))
    print("alternative routes (different calls, same outcome): %d tasks, all pass check" % len(_ALT_ROUTES))
    print("fuzz: %d calls, 0 exceptions, state unchanged on every error" % _calls)
    print("OK %d/%d" % (_ok, len(TASKS)))
