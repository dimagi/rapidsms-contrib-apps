#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

import re
from datetime import datetime, timedelta
import rapidsms
from reporters.models import *
from models import *


class App (rapidsms.app.App):
    """When an incoming message is received, this application is notified
       last, to grab and log the message as a "free-text" message, to be
       displayed in the WebUI with no automatic response from RapidSMS.

       Also, this app receives outgoing messages from the WebUI (via the
       AJAX app), and relays them to the router."""

    PRIORITY = "lowest"


    def handle(self, msg):
        if not msg.responses:

            # log the message, along with the identity
            # information provided by reporters.app/parse
            msg = IncomingMessage.objects.create(
                received=datetime.now(),
                text=msg.text,
                **msg.persistance_dict)

            self.info("Message %d captured" % (msg.pk))

            # short-circuit, since this message is dealt
            # with now (even if it shouldn't have been)
            return True


    # NOTE: outgoing messages are not logged here via the "outoging"
    # hook, since we're not interested in ALL outgoing messages; only
    # those that were sent from within the messaging UI (below)


    def ajax_POST_send_message(self, params, form):
        rep = Reporter.objects.get(pk=form["uid"])

        # if this message contains the same text as the _previous_ message sent,
        # and is within 6 hours, we'll recycle it (since it has-many recipients)
        try:
            time_limit = datetime.now() - timedelta(hours=6)
            msg = OutgoingMessage.objects.filter(
                sent__gt=time_limit,
                text=form["text"])[0]

        # no match, so create a new outgoing message for
        # this recipient (it might be the first of many)
        except IndexError:
            msg = OutgoingMessage.objects.create(
                sent=datetime.now(),
                text=form["text"])

        # attach this recipient to
        # the (old or new) message
        msg.recipients.create(
            reporter=rep)

        # abort if we don't know where to send the message to
        # (if the device the reporter registed with has been
        # taken by someone else, or was created in the WebUI)
        pconn = rep.connection()
        if pconn is None:
            raise Exception("%s is unreachable (no connection)" % rep)

        # abort if we can't find a valid backend. PersistantBackend
        # objects SHOULD refer to a valid RapidSMS backend (via their
        # slug), but sometimes backends are removed or renamed.
        be = self.router.get_backend(pconn.backend.slug)
        if be is None:
            raise Exception(
                "No such backend: %s" %
                pconn.backend.title)
        
        # attempt to send the message
        # TODO: what could go wrong here?
        return be.message(pconn.identity, form["text"]).send()

    def start(self):
        # regex to match @alias or @pk
        self.alias_pattern= re.compile("(\s*@\w+\s*)")
        # TODO #grouptitle

    def handle(self, message):
        # FIXME this is a crappy rough draft
        router = self.router
        # gather possible @aliases and @pks occuring in message's text
        possible_reportees = re.finditer(self.alias_pattern, message.text)
        response = ''
        win = []
        fail = []
        for possible_reportee in possible_reportees:
            # pull the @alias or @pk from the match object
            raw_reportee = possible_reportee.group(0)
            # lookup the alias or pk
            reportee = Reporter.lookup(raw_reportee.replace('@','').strip())
            if reportee:
                # TODO only say its a success if its successful
                #if reportee.send(router, message):
                reportee.send(router, message)
                # add to list of successes
                win.append(raw_reportee)
            else:
                # add to list of failures
                fail.append(raw_reportee)
        if len(win) > 0:
            response = response + "Message sent to %s." % (', '.join(win))
        if len(fail) > 0:
            response = response + "No user found for %s." % (', '.join(fail))
        # respond with successes and failures
        return self._send_message(pconn, form["text"])
        
    def ajax_POST_send_message_to_connection(self, params, form):
        '''Sends a message using a connection id, instead of
           a reporter id.'''
        # todo: this method doesn't deal with logging.  should it?
        # possibly not, since there is no UI for this on the messaging
        # tab.  This is just a convenience for other apps.  
        connection = PersistantConnection.objects.get(pk=form["connection_id"])
        return self._send_message(connection, form["text"])
        
    
    def _send_message(self, connection, message_body):    
        '''Attempts to send a message througha given connection'''
        # abort if we can't find a valid backend. PersistantBackend
        # objects SHOULD refer to a valid RapidSMS backend (via their
        # slug), but sometimes backends are removed or renamed.
        be = self.router.get_backend(connection.backend.slug)
        if be is None:
            raise Exception(
                "No such backend: %s" %
                connection.backend.title)
        
        # attempt to send the message
        # TODO: what could go wrong here?
        return be.message(connection.identity, message_body).send()
