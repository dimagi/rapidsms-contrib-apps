#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


import rapidsms
from reporters.models import PersistantConnection
from models import OutgoingMessage, IncomingMessage


class App(rapidsms.app.App):
    # save messages on 'parse' so that 
    # annotations can be added to persistent message object by other apps
    def parse(self, msg):
        # make and save messages on their way in and 
        # cast connection as string so pysqlite doesnt complain
        text_to_save = msg.text
        if len(msg.text) > MAX_LATIN_SMS_LEN:
            text_to_save = msg.text[0:160]
        message = IncomingMessage.objects.create(
            text=text_to_save, **self._who(msg))
        msg.persistent_msg = message
        self.debug(message)
    
    def outgoing(self, message):
        # make and save messages on their way out and 
        # cast connection as string so pysqlite doesnt complain
        msg = OutgoingMessage.objects.create(
            text=message.text, **self._who(msg))
        self.debug(msg.text)
        # inject this id into the message object.
        message.logger_id = msg.id;

    def _who(self, msg):
        return PersistantConnection.from_message(msg).dict

