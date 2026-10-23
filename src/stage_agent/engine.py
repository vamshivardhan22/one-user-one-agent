from __future__ import annotations
from datetime import timedelta
import time
from .timeutil import parse_time, iso, age_seconds, ist_day, is_quiet_hours

FORBIDDEN_PUSH = ("last chance", "hurry", "only today", "free forever", "guaranteed")
ALLOWED_ROWS = {"next_episode", "because_you_watched", "popular_in_dialect", "new_releases", "genre"}

def first(row, *keys, default=None):
    for key in keys:
        if row.get(key) not in (None, ""):
            return row[key]
    return default

def truth(value):
    return str(value).strip().lower() in {"true", "1", "yes", "y", "opted_in"}

def as_bool(value):
    return value if isinstance(value, bool) else truth(value)

class AgentEngine:
    """Deterministic baseline. Policy verification does not rely on model output."""
    def __init__(self, pack: dict, store, max_trigger_age_s=300, max_model_calls=8, max_tool_calls=20):
        self.pack, self.store = pack, store
        self.max_trigger_age_s, self.max_model_calls, self.max_tool_calls = max_trigger_age_s, max_model_calls, max_tool_calls
        self.events = pack.get("events", [])
        self.profiles = pack.get("profiles", [])
        self.catalogue = pack.get("catalogue", [])
        self.goals = pack.get("goals", [])
        self.interventions = pack.get("interventions", {})
        self.arms = pack.get("arms", {})

    def _viewer_events(self, viewer_id):
        return [event for event in self.events if str(first(event, "viewer_id", "user_id")) == str(viewer_id)]

    def _profile(self, viewer_id):
        rows = [profile for profile in self.profiles if str(first(profile, "viewer_id", "user_id")) == str(viewer_id)]
        if not rows:
            return {}
        def ordering(profile):
            timestamp = parse_time(first(profile, "snapshot_at", "updated_at", "date", "as_of"))
            return (timestamp.timestamp() if timestamp else -1, str(sorted(profile.items())))
        return sorted(rows, key=ordering)[-1]

    def _fact(self, value, source, timestamp=None, freshness="unknown"):
        return {"value": value, "source": source, "timestamp": timestamp, "freshness": freshness}

    def resolve_facts(self, viewer_id, trigger):
        events = self._viewer_events(viewer_id)
        profile = self._profile(viewer_id)
        conflicts = []
        app_dialect = first(trigger, "app_dialect", "dialect")
        profile_dialect = first(profile, "preferred_dialect", "dialect", "app_dialect")
        if app_dialect and profile_dialect and app_dialect != profile_dialect:
            conflicts.append({"fact":"dialect","chosen":"app_setting","app_setting":app_dialect,"profile":profile_dialect})
        def name(event):
            return str(first(event, "event_name", "event_type", "name", default="")).lower()
        purchases = sorted([event for event in events if name(event) in {"purchase","subscription_purchased","payment_success"}],
                           key=lambda event: str(first(event,"received_at",default="")))
        optouts = sorted([event for event in events if name(event) in {"notification_opt_out","push_opt_out"}],
                         key=lambda event: str(first(event,"received_at",default="")))
        signups = sorted([event for event in events if name(event) == "signup_completed"],
                          key=lambda event: str(first(event,"received_at",default="")))
        subscription = "paid" if purchases else first(profile, "subscription_status", "subscription", default="unknown")
        notification_opt_in = False if optouts else as_bool(first(profile, "notifications_opt_in", "push_opt_in", default=False))
        whatsapp_opt_in = as_bool(first(profile, "whatsapp_opt_in", default=False))
        signup = first(profile, "signup_at", "signup_date")
        if signups:
            signup = first(signups[-1], "received_at", "occurred_at", default=signup)
        facts = {
            "dialect": self._fact(app_dialect or profile_dialect, "app_setting" if app_dialect else "profile", first(trigger,"received_at"), "current_trigger" if app_dialect else "snapshot"),
            "subscription": self._fact(subscription, "purchase_event" if purchases else "profile_snapshot", first(purchases[-1],"received_at") if purchases else first(profile,"snapshot_at","updated_at"), "event" if purchases else "possibly_stale"),
            "notifications_opt_in": self._fact(notification_opt_in, "opt_out_event" if optouts else "profile_snapshot", first(optouts[-1],"received_at") if optouts else first(profile,"snapshot_at","updated_at"), "event" if optouts else "possibly_stale"),
            "whatsapp_opt_in": self._fact(whatsapp_opt_in, "profile_snapshot", first(profile,"snapshot_at","updated_at"), "possibly_stale"),
            "signup_at": self._fact(signup, "signup_event" if signups else "profile_snapshot", signup, "event" if signups else "possibly_stale"),
        }
        return facts, conflicts, events

    def _goal_candidates(self, facts, events):
        event_names = {str(first(event,"event_name","event_type","name",default="")).lower() for event in events}
        candidates = []
        for goal in self.goals:
            success_signal = first(goal,"success_event","success_signal","success_event_name")
            if not success_signal:
                continue
            eligibility = first(goal,"eligibility","eligibility_rule",default={})
            if isinstance(eligibility, dict):
                required_event = first(eligibility,"requires_event","event")
                if required_event and str(required_event).lower() not in event_names:
                    continue
                required_subscription = first(eligibility,"subscription_status","subscription")
                if required_subscription and str(facts["subscription"]["value"]).lower() != str(required_subscription).lower():
                    continue
            elif str(eligibility).strip().lower() in {"false","never"}:
                continue
            candidates.append(goal)
        return candidates

    def _available_titles(self, dialect, now):
        variants = []
        for title in self.catalogue:
            if str(first(title,"dialect","app_dialect","language_variant")) != str(dialect):
                continue
            start = parse_time(first(title,"available_from","start_at","publish_at"))
            end = parse_time(first(title,"available_until","end_at","withdrawn_at"))
            if start and now and now < start: continue
            if end and now and now >= end: continue
            title_id = first(title,"title_id","id")
            slug = first(title,"content_slug","slug",default=title_id)
            if title_id is not None and slug is not None:
                variants.append((str(slug),title))
        deduplicated = {}
        for slug,title in sorted(variants,key=lambda pair:str(first(pair[1],"title_id","id"))):
            deduplicated.setdefault(slug,title)
        return list(deduplicated.values())

    def _plan_home(self, dialect, now):
        titles = self._available_titles(dialect,now)
        if len(titles) < 3:
            return None
        chosen = titles[:min(10,len(titles))]
        return {"action":"HOME_PAGE","hero_title_id":first(chosen[0],"title_id","id"),
                "rows":[{"type":"popular_in_dialect","titles":[{"title_id":first(title,"title_id","id"),
                "content_slug":first(title,"content_slug","slug"),"title":first(title,"title","name")} for title in chosen]}],
                "ttl_minutes":120}

    def _choose_action(self, facts, goal, now):
        home = self._plan_home(facts["dialect"]["value"],now)
        return home or {"action":"NO_ACTION","reason":"No valid home-page row with at least three available titles; no verified message plan."}

    def verify(self, viewer_id, trigger, facts, action, now, event_id):
        passed, failed = [], []
        if str(self.arms.get(str(viewer_id),"agent")).lower() == "holdout":
            failed.append({"check":"holdout","reason":"Holdout viewers must receive zero interventions."})
        else:
            passed.append("holdout")
        age = age_seconds(first(trigger,"received_at","deliver_at"),first(trigger,"occurred_at","sent_at"))
        if age is not None and age > self.max_trigger_age_s:
            failed.append({"check":"trigger_freshness","reason":f"Trigger age {int(age)}s exceeds {self.max_trigger_age_s}s."})
        else:
            passed.append("trigger_freshness")
        if action["action"] == "HOME_PAGE":
            title_rows = []
            for row in action.get("rows",[]):
                if row.get("type") not in ALLOWED_ROWS:
                    failed.append({"check":"row_type","reason":"Unsupported home row type."})
                row_titles = row.get("titles",[])
                title_rows.extend(row_titles)
                if not 3 <= len(row_titles) <= 10:
                    failed.append({"check":"row_size","reason":"Home rows require 3-10 titles."})
            if len(action.get("rows",[])) > 6:
                failed.append({"check":"row_count","reason":"A page may contain at most six rows."})
            slugs = [title["content_slug"] for title in title_rows]
            if len(slugs) != len(set(slugs)):
                failed.append({"check":"content_slug_dedupe","reason":"Duplicate content_slug on the page."})
            allowed_ids = {str(first(title,"title_id","id")) for title in self._available_titles(facts["dialect"]["value"],now)}
            if not {str(title["title_id"]) for title in title_rows}.issubset(allowed_ids):
                failed.append({"check":"dialect_availability","reason":"A page title is unavailable or mismatched to the active dialect."})
            else:
                passed.append("dialect_availability")
            if not any(item["check"] in {"row_type","row_size","row_count","content_slug_dedupe"} for item in failed):
                passed.append("home_page_shape")
        elif action["action"] in {"PUSH","WHATSAPP"}:
            day = ist_day(iso(now))
            if is_quiet_hours(iso(now)):
                failed.append({"check":"quiet_hours","reason":"Messaging is prohibited from 22:00 to 08:00 IST."})
            if self.store.prior_message_today(viewer_id,day):
                failed.append({"check":"frequency_cap","reason":"A push or WhatsApp already exists for this viewer's IST day."})
            if action["action"] == "PUSH":
                message = str(action.get("title",""))+" "+str(action.get("body",""))
                if len(str(action.get("title",""))) > 40 or len(str(action.get("body",""))) > 120 or any(phrase in message.lower() for phrase in FORBIDDEN_PUSH):
                    failed.append({"check":"push_copy","reason":"Push copy violates length or forbidden phrase rules."})
                if not facts["notifications_opt_in"]["value"]:
                    failed.append({"check":"consent","reason":"Push consent is not confirmed."})
            elif not facts["whatsapp_opt_in"]["value"]:
                failed.append({"check":"consent","reason":"WhatsApp consent is not confirmed."})
            if action["action"] == "WHATSAPP" and action.get("template_id") not in set(self.interventions.get("approved_whatsapp_templates",[])):
                failed.append({"check":"whatsapp_template","reason":"WhatsApp template is not approved."})
        if not failed: passed.append("independent_verifier")
        return {"passed":passed,"failed":failed}

    def decide(self, trigger):
        started = time.perf_counter()
        viewer_id = str(first(trigger,"viewer_id","user_id",default="UNKNOWN"))
        event_id = str(first(trigger,"event_id","id",default=""))
        if event_id and self.store.get_decision(event_id):
            return self.store.get_decision(event_id)
        received = parse_time(first(trigger,"received_at","deliver_at"))
        occurred = parse_time(first(trigger,"occurred_at","sent_at"))
        now = received or occurred or parse_time("1970-01-01T00:00:00Z")
        facts, conflicts, events = self.resolve_facts(viewer_id,trigger)
        candidates = self._goal_candidates(facts,events)
        goal = None
        if candidates:
            chosen_goal = candidates[0]
            try: window = int(first(chosen_goal,"window_days","deadline_days",default=3))
            except (TypeError,ValueError): window = 3
            goal = {"id":first(chosen_goal,"id","goal_id","key"),"deadline":iso(now+timedelta(days=window)),
                    "success_signal":first(chosen_goal,"success_event","success_signal","success_event_name")}
        proposed = self._choose_action(facts,goal,now) if candidates else {"action":"NO_ACTION","reason":"No eligible goal with a measurable success signal was established from supplied evidence."}
        checks = self.verify(viewer_id,trigger,facts,proposed,now,event_id)
        final_action = proposed
        if checks["failed"]:
            final_action = {"action":"NO_ACTION","reason":"Independent verifier rejected the proposed action.","rejected_action":proposed}
        elapsed = round((time.perf_counter()-started)*1000,3)
        evidence = [{"ref":f"event:{first(event,'event_id','id')}","source":"events","received_at":first(event,"received_at"),"freshness":"derived from received_at"}
                    for event in events[-20:] if first(event,"event_id","id") is not None]
        decision = {
            "decision_id":f"D-{event_id or viewer_id+'-'+str(int(time.time()*1000))}","viewer_id":viewer_id,
            "trigger":{"event":first(trigger,"event_name","event_type","name",default="app_open"),"event_id":event_id,
                       "received_at":iso(received),"event_age_s":age_seconds(first(trigger,"received_at"),first(trigger,"occurred_at","sent_at"))},
            "goal":goal,"action":final_action["action"],
            "action_payload":final_action if final_action["action"] != "NO_ACTION" else None,
            "no_action_reason":final_action.get("reason") if final_action["action"] == "NO_ACTION" else None,
            "dialect":{"used":facts["dialect"]["value"],"source":facts["dialect"]["source"],"conflicts":conflicts},
            "confidence":0.75 if goal else 0.35,
            "confidence_reason":"Heuristic confidence from deterministic rules; not a calibrated probability.",
            "evidence":evidence,"facts":facts,
            "assumptions":["Only supplied pack facts are authoritative.","Ambiguous eligibility is not inferred."],
            "checks":checks,"decided_in_ms":elapsed,"model_calls":0,"tool_calls":0,
            "fallback_used":False,"status":"PUBLISHED" if final_action["action"] != "NO_ACTION" else "ABSTAINED","rule_version":"1.0.0"}
        if event_id: self.store.save_decision(event_id,decision)
        state = self.store.get_viewer(viewer_id)
        state["facts"],state["active_goal"] = facts,goal
        state.setdefault("history",[]).append({"decision_id":decision["decision_id"],"event_id":event_id,"action":decision["action"],"at":iso(now)})
        self.store.save_viewer(viewer_id,state)
        if decision["action"] == "HOME_PAGE" and event_id:
            self.store.save_action(event_id,viewer_id,"HOME_PAGE",decision["action_payload"],ist_day(iso(now)))
        return decision

def deduplicate_events(events):
    seen, output = set(), []
    for event in events:
        event_id = first(event,"event_id","id")
        if event_id is None:
            output.append(event)
        elif str(event_id) not in seen:
            seen.add(str(event_id))
            output.append(event)
    return output
