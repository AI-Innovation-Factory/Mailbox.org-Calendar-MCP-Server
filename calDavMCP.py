from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
import caldav
from caldav.collection import Principal
import vobject
from dotenv import load_dotenv
import os
import uuid
from datetime import datetime
from typing import Literal
from datetime import timedelta
from typing import Optional

load_dotenv()

mcp = FastMCP(name="caldav-mcp",
              instructions="""This server provides a way to interact with caldav."""
              )


principal: Optional[Principal] = None
creatoremail = os.getenv('CDUSERNAME') # used for a edge case


def get_principal() -> Principal:
    """
    Lazy-loader for the CalDAV principal. 
    Ensures we only connect when a tool is actually used.
    """
    global principal
    
    if principal is not None:
        return principal

    url = os.getenv('CDURL')
    username = os.getenv('CDUSERNAME')
    password = os.getenv('CDPASSWORD')

    if not all([url, username, password]):
        raise RuntimeError("Missing CalDAV environment variables (CDURL, CDUSERNAME, or CDPASSWORD)")

    try:
        client = caldav.DAVClient(
            url=url,
            username=username,
            password=password,
        )
        principal = client.principal()
        
        principal.calendars() 
        
        print(f"Successfully connected to CalDAV for {username}")
        principal = principal
        return principal

    except Exception as e:
        print(f"CalDAV Connection Failed: {e}")
        raise RuntimeError(f"Could not connect to CalDAV server: {e}")


def getCalendar(calendarName: str, principal: Principal):
    try:
        calendars = principal.calendars()
        calendar = next((cal for cal in calendars if cal.get_display_name() == calendarName), None)
        
        if not calendar:
            raise ValueError(f"Calendar '{calendarName}' not found. Available: {[c.get_display_name() for c in calendars]}")
        return calendar
    except Exception as e:
        return f"Error conneting to/finding calendar. Error: {e}"


def isoToDT(iso: str) -> datetime:
    try:
        return datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(vobject.icalendar.utc)
    except ValueError as e:
        raise ValueError(f"Invalid ISO format: {iso}")


@mcp.tool()
def getCalendarEvents(
                      start_iso: str,
                      end_iso: str,
                      ) -> dict:
    """
    Returns all calendar events the user has between the given start and end times.
    
    CRITICAL RULES FOR LLM:
    1. All times must be passed in strict UTC ISO 8601 format (example. '2026-03-16T15:00:00Z' or '2026-03-19 13:00:00+02:00' or '2026-03-25T09:00:00Z').
    
    Args:
        start_iso: The start time in ISO 8601 format (e.g., '2026-03-16T15:00:00Z')
        end_iso: The end time in ISO 8601 format
    """
    
    principal = get_principal()
    calendars = principal.calendars()
    eventlist = {}
        
    for calendar in calendars:
        eventlist[calendar.get_display_name()] = []
        events = calendar.search(event=True, start=isoToDT(start_iso), end=isoToDT(end_iso))
            
        for event in events:
            v_event = event.vobject_instance.vevent
            eventlist[calendar.get_display_name()].append({"type": "text", "text": v_event})
    return eventlist


@mcp.tool()
def createCalendarEvent(
                        eventSummary: str,
                        start_iso: str,
                        end_iso: str,
                        calendar_name: str = "Calendar",
                        particimantMails: list[str] = [],
                        description: str = "",
                        location: str = "",
                        recurring_rule: str = ""
                        ) -> str:
    """
    Creates a calendar event and shares it to participants if they are given
    
    CRITICAL RULES FOR LLM:
    1. All times must be passed in strict UTC ISO 8601 format (example. '2026-03-16T15:00:00Z' or '2026-03-19 13:00:00+02:00' or '2026-03-25T09:00:00Z').
    
    Args:
        start_iso: The start time in ISO 8601 format (e.g., '2026-03-16T15:00:00Z')
        end_iso: The end time in ISO 8601 format
        calendar_name: The name of the calendar (e.g., 'Calendar', 'Events')
        recurring_rule: When the event recurs, recurring rules:
            FREQ: DAILY, WEEKLY, MONTHLY, YEARLY
            INTERVAL: how often
            COUNT: how many times
            UNTIL: DateTime (UTC) (e.g. UNTIL=20261231T235959Z)
            BYDAY: MO, TU, WE, TH, FR, SA, SU
            BYMONTHDAY: 1 to 31 (or -1 to -31)
            BYMONTH: 1 to 12
            BYYEARDAY: 1 to 366
            BYWEEKNO: 1 to 53
            (Example: 'FREQ=WEEKLY;COUNT=5;BYDAY=MO')"
    """
    
    principal = get_principal()
    calendar = getCalendar(calendar_name, principal)
    eventuid = str(uuid.uuid4())
    
    cal = vobject.iCalendar()
    vevent = cal.add('vevent')
        
    vevent.add('summary').value = eventSummary
    vevent.add('dtstart').value = isoToDT(start_iso)
    vevent.add('dtend').value = isoToDT(end_iso)
    vevent.add('uid').value = eventuid
        
    if description:
        vevent.add('description').value = description
    if location:
        vevent.add('location').value = location
    if recurring_rule:
        vevent.add('rrule').value = recurring_rule
        
    for attendeeMail in particimantMails:
        attendee = vevent.add('attendee')
        attendee.value = f'mailto:{attendeeMail}'
        attendee.params['RSVP'] = ['TRUE']
        attendee.params['PARTSTAT'] = ['NEEDS-ACTION']
        
    print(cal.serialize())
    calendar.add_event(cal.serialize())
    return f"calendar event successfully added, the added events uid is '{eventuid}'"


@mcp.tool()
def deleteCalendarEvent(
                              uid: str,
                              start_iso: str,
                              end_iso: str,
                              calendar_name: str = "Calendar",
                              delete_mode: Literal["all", "this", "future"] = "all"
                              ) -> str:
    """
    Deletes existing CalDAV calendar event.
    
    CRITICAL RULES FOR LLM:
    1. ALWAYS look up the event first to get the correct `uid` before calling `deleteCalendarEvent`.
    2. All times must be passed in strict UTC ISO 8601 format (example: '2026-03-16T15:00:00Z').
    3. Never attempt to guess an event's UID.
    
    Args:
        uid: The unique 'UID' property of the VEVENT to be deleted.
        start_iso: The start time for the event in ISO 8601 format (e.g., '2026-03-16T15:00:00Z')
        end_iso: The end time for the event in ISO 8601 format
        calendar_name: The name of the calendar (e.g., 'Calendar', 'Birthdays')
        delete_mode: The scope of deletion. 'all' (entire series), 'this' (only this specific instance), or 'future' (this instance and all following). Default is 'all'.
    """
    
    principal = get_principal()
    calendar = getCalendar(calendar_name, principal)
    
    try:
        events = calendar.search(event=True, start=isoToDT(start_iso), end=isoToDT(end_iso))
    
        if len(events) == 0:
            return "no events found with given parameters"
        
        event = next((e for e in events if e.vobject_instance.vevent.uid.value == uid), None)
        if not event:
            return f"No event found with UID: {uid}"
    except Exception:
        return f"No event found to delete with UID: {uid}"

    vobj = event.vobject_instance
    vevent = vobj.vevent

    if delete_mode == "all":
        event.delete()
        print("Entire event series deleted successfully.")
        return "calendar event series successfully deleted"

    target_dt = isoToDT(start_iso)

    if delete_mode == "this":
        vevent.add('exdate').value = [target_dt]
        event.save()
        print("Single occurrence deleted via EXDATE.")
        return "single calendar event occurrence successfully deleted"

    elif delete_mode == "future":
        if hasattr(vevent, 'rrule'):
            rrule_str = vevent.rrule.value
            
            until_dt = target_dt - timedelta(seconds=1)
            until_str = until_dt.strftime('%Y%m%dT%H%M%SZ')

            parts = [p for p in rrule_str.split(';') if not p.startswith(('UNTIL=', 'COUNT='))]
            parts.append(f"UNTIL={until_str}")
            
            vevent.rrule.value = ";".join(parts)
            event.save()
            
            print("Event truncated. Future occurrences deleted.")
            return "calendar event and all future occurrences successfully deleted"
        else:
            event.delete()
            print("Event deleted (was not recurring).")
            return "calendar event successfully deleted"

@mcp.tool()
def updateCalendarEvent(
                        uid: str,
                        start_iso: str,
                        end_iso: str,
                        calendar_name: str = "Calendar",
                        
                        new_eventSummary: str = "",
                        new_start_iso: str = "",
                        new_end_iso: str = "",
                        new_particimant_mails: list[str] = [],
                        attendees_to_remove: list[str] = [],
                        new_description: str = "",
                        new_location: str = "",
                        new_recurring_rule: str = ""
                        ) -> str:
    """
    Updates a existing CalDAV calendar event.
    
    CRITICAL RULES FOR LLM:
    1. ALWAYS look up the event first to get the correct `uid` before calling `updateCalendarEvent`.
    2. All times must be passed in strict UTC ISO 8601 format (example. '2026-03-16T15:00:00Z' or '2026-03-19 13:00:00+02:00' or '2026-03-25T09:00:00Z').
    3. Never attempt to guess an event's UID.
    
    Args:
        uid: The unique 'UID' property of the VEVENT to be deleted.
        start_iso: The start time for the event in ISO 8601 format (e.g., '2026-03-16T15:00:00Z')
        end_iso: The end time for the event in ISO 8601 format
        calendar_name: The name of the calendar (e.g., 'Calendar', 'Birthdays')
        new_particimantMails: the list of participants to add
        new_recurring_rule: When the event recurs, recurring rules:
            FREQ: DAILY, WEEKLY, MONTHLY, YEARLY
            INTERVAL: how often
            COUNT: how many times
            UNTIL: DateTime (UTC) (e.g. UNTIL=20261231T235959Z)
            BYDAY: MO, TU, WE, TH, FR, SA, SU
            BYMONTHDAY: 1 to 31 (or -1 to -31)
            BYMONTH: 1 to 12
            BYYEARDAY: 1 to 366
            BYWEEKNO: 1 to 53
            (Example: 'FREQ=WEEKLY;COUNT=5;BYDAY=MO')"
    """
    
    principal = get_principal()
    calendar = getCalendar(calendar_name, principal)
    
    events = calendar.search(event=True, start=isoToDT(start_iso), end=isoToDT(end_iso))
    
    if len(events) == 0:
        return "no events found with given parameters"
    
    event = next((e for e in events if e.vobject_instance.vevent.uid.value == uid), None)
    if not event:
        return f"No event found with UID: {uid}"
    
    v_obj = event.vobject_instance
    vevent = v_obj.vevent
    
    # try to find organizer from the event but if cant be found then most likely user is organizer themselves
    if hasattr(vevent, 'organizer'):
        organizer = vevent.organizer.value
    else:
        organizer = f"mailto:{creatoremail}"
    
    if hasattr(vevent, 'sequence'):
        try:
            vevent.sequence.value = str(int(vevent.sequence.value) + 1)
        except ValueError:
            vevent.sequence.value = '1'
    else:
        vevent.add('sequence').value = '1'
    
    updates = {
        'summary': new_eventSummary,
        'dtstart': isoToDT(new_start_iso) if new_start_iso else None,
        'dtend': isoToDT(new_end_iso) if new_end_iso else None,
        'description': new_description,
        'location': new_location,
        'rrule': new_recurring_rule
    }

    for key, value in updates.items():
        if value:
            if hasattr(vevent, key):
                getattr(vevent, key).value = value
            else:
                vevent.add(key).value = value
                
    if attendees_to_remove and 'attendee' in vevent.contents:
        to_remove = [f"mailto:{m.lower()}" for m in attendees_to_remove 
                     if f"mailto:{m.lower()}" != organizer]
        
        vevent.contents['attendee'] = [
            a for a in vevent.contents['attendee'] 
            if a.value.lower() not in to_remove
        ]
    
    if new_particimant_mails:
        existing_emails = [a.value.lower() for a in vevent.contents.get('attendee', [])]
        
        for mail in new_particimant_mails:
            mailto_link = f'mailto:{mail}'.lower()
            if mailto_link not in existing_emails:
                attendee = vevent.add('attendee')
                attendee.value = f'mailto:{mail}'
                attendee.params['RSVP'] = ['TRUE']
                attendee.params['PARTSTAT'] = ['NEEDS-ACTION']
                
    attendee_emails = [a.value.lower() for a in vevent.contents.get('attendee', [])]
        
    if organizer not in attendee_emails:
        org_att = vevent.add('attendee')
        org_att.value = organizer
        org_att.params['PARTSTAT'] = ['ACCEPTED']
        org_att.params['RSVP'] = ['FALSE']
        org_att.params['ROLE'] = ['CHAIR']
    
    event.data = v_obj.serialize()
    event.save()
    return "event successfully updated"


@mcp.prompt()
def manage_calendar_instructions() -> str:
    """Provides the LLM with strict instructions on how to use the CalDAV tools."""
    return """
    You are an expert calendar assistant. When managing the user's CalDAV calendar, strictly adhere to these rules:
    
    1. ALWAYS look up the event first to get the correct `uid` before calling `updateCalendarEvent` or `deleteCalendarEvent`.
    2. All times must be passed in strict UTC ISO 8601 format (example. '2026-03-16T15:00:00Z' or '2026-03-19 13:00:00+02:00' or '2026-03-25T09:00:00Z').
    3. Never attempt to guess an event's UID.
    4. Never guess the date, if it isn't known, ask the user for the date.
    """


if __name__ == "__main__":
    print("Starting mcp server...")
    mcp.run(transport="sse")
