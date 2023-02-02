#
# Ioreth - An APRS library and bot
# Copyright (C) 2020  Alexandre Erwin Ittner, PP5ITT <alexandre@ittner.com.br>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#
# ========
#
# This fork of Ioreth was modified by Angelo N2RAC/DU2XXR to support additional
# functionalities, such as a means to store callsigns from a "net" checkin
# as well as a means to forward messages to all stations checked in for the day
# It is also supported by local cron jobs on my own machine and web server
# to publish the net log on a regular basis.
# 
# Pardon my code. My knowledge is very rudimentary, and I only modify or create
# functions as I need them. If anyone can help improve on the code and the
# logic of this script, I would very much appreciate it.
# You may reach me at qsl@n2rac.com or simply APRS message me at DU2XXR-7.
#
# A lot of the items here are still poorly documented if at all. Many also
# rely on some weird or nuanced scripts or directory structures that I have
# maintained on my own machine or server, so bear with me.
# The non-indented comments are mine. The indented ones are by Alexandre.
# A lot of this is trial-and-error for me, so again, please bear with me.
#
# 2023-02-02 0322H

import sys
import time
import logging
import configparser
import os
import re
import random
import urllib
import requests
import json
import datetime

logging.basicConfig()
logger = logging.getLogger(__name__)

from cronex import CronExpression
from .clients import AprsClient
from . import aprs
from . import remotecmd
from . import utils
from os import path
from urllib.request import urlopen, Request


# These lines below I have added in order to provide a means for ioreth to store
# and retrieve a list of "net" checkins on a daily basis. I did not bother to use
# more intuitive names for the files, but I can perhaps do so in a later code cleanup.

timestr = time.strftime("%Y%m%d")
filename1 = "/home/pi/ioreth/ioreth/ioreth/netlog-"+timestr
filename2 = "home/pi/ioreth/ioreth/ioreth/netlog-msg"
filename3 = "/home/pi/ioreth/ioreth/ioreth/netlog-"+timestr+"-cr"
cqmesg = "/home/pi/ioreth/ioreth/ioreth/cqlog/cqmesg"
cqlog = "/home/pi/ioreth/ioreth/ioreth/cqlog/cqlog"
dusubs = "/home/pi/ioreth/ioreth/ioreth/dusubs"
dusubslist = "/home/pi/ioreth/ioreth/ioreth/dusubslist"
file = open(filename1, 'a')
file = open(filename3, 'a')
icmesg = "/home/pi/ioreth/ioreth/ioreth/eric/icmesg"
iclist = "/home/pi/ioreth/ioreth/ioreth/eric/iclist"
iclog = "/home/pi/ioreth/ioreth/ioreth/eric/eric"
iclast = "/home/pi/ioreth/ioreth/ioreth/eric/iclast"
iclatest = "/home/pi/ioreth/ioreth/ioreth/eric/iclatest"

# Also Mmoved time string to place where it can be reset at midnight

def is_br_callsign(callsign):
    return bool(re.match("P[PTUY][0-9].+", callsign.upper()))


class BotAprsHandler(aprs.Handler):
    def __init__(self, callsign, client):
        aprs.Handler.__init__(self, callsign)
        self._client = client

    def on_aprs_message(self, source, addressee, text, origframe, msgid=None, via=None):
        """Handle an APRS message.

        This may be a directed message, a bulletin, announce ... with or
        without confirmation request, or maybe just trash. We will need to
        look inside to know.
        """

        if addressee.strip().upper() != self.callsign.upper():
            # This message was not sent for us.
            return

        if re.match(r"^(ack|rej)\d+", text):
            # We don't ask for acks, but may receive them anyway. Spec says
            # acks and rejs must be exactly "ackXXXX" and "rejXXXX", case
            # sensitive, no spaces. Be a little conservative here and do
            # not try to interpret anything else as control messages.
            logger.info("Ignoring control message %s from %s", text, source)
            return

#        self.handle_aprs_msg_bot_query(source, text, origframe)
        if msgid:
            # APRS Protocol Reference 1.0.1 chapter 14 (page 72) says we can
            # reject a message by sending a rejXXXXX instead of an ackXXXXX
            # "If a station is unable to accept a message". Not sure if it is
            # semantically correct to use this for an invalid query for a bot,
            # so always acks.
            logger.info("Sending ack to message %s from %s.", msgid, source)
            self.send_aprs_msg(source.replace('*',''), "ack" + msgid)

        self.handle_aprs_msg_bot_query(source, text, origframe)


    def handle_aprs_msg_bot_query(self, source, text, origframe):
        """We got an text message direct to us. Handle it as a bot query.
        TODO: Make this a generic thing.

        source: the sender's callsign+SSID
        text: message text.
        """

        sourcetrunc = source.replace('*','')
        qry_args = text.lstrip().split(" ", 1)
        qry = qry_args[0].lower()
        args = ""
        if not os.path.isfile(filename1):
            file = open(filename1, 'w')
        if not os.path.isfile(filename3):
            file = open(filename3, 'w')
        if len(qry_args) == 2:
            args = qry_args[1]

        random_replies = {
            "moria": "Pedo mellon a minno",
            "mellon": "*door opens*",
            "mellon!": "**door opens**  🚶🚶🚶🚶🚶🚶🚶🚶🚶  💍→🌋",
            "meow": "=^.^=  purr purr  =^.^=",
            "clacks": "GNU Terry Pratchett",
            "73": "73 🖖",
        }

        if sourcetrunc == "APRSPH" or sourcetrunc == "ANSRVR" :
                  logger.info("Message from ignore list. Stop processing." )
                  return
#        if sourcetrunc == "ANSRVR":
#                  logger.info("Message from ANSRVR. Stop processing." )
#                  return



        if qry == "ping":
            self.send_aprs_msg(sourcetrunc, "Pong! " + args )
        elif qry == "test":
#                                            1234567890123456789012345678901234567890123456789012345678901234567
            self.send_aprs_msg(sourcetrunc, "It works! CQ[space]msg to chckin. https://aprsph.net for more cmds.")
        elif qry == "?aprst" or qry == "?ping?" or qry == "aprst?" or qry == "aprst" :
            tmp_lst = (
                origframe.to_aprs_string()
                .decode("utf-8", errors="replace")
                .split("::", 2)
            )
            self.send_aprs_msg(sourcetrunc, tmp_lst[0] + ":")
        elif qry == "version":
            self.send_aprs_msg(sourcetrunc, "Python " + sys.version.replace("\n", " "))
        elif qry == "about":
            self.send_aprs_msg(sourcetrunc, "APRS bot by N2RAC/DU2XXR based on ioreth by PP5ITT. aprsph.net" )
        elif qry == "time":
            self.send_aprs_msg(
                sourcetrunc, "Localtime is " + time.strftime("%Y-%m-%d %H:%M:%S %Z")
            )
        elif qry == "help":
#                                            1234567890123456789012345678901234567890123456789012345678901234567
            self.send_aprs_msg(sourcetrunc, "CQ [space] msg to join net & send msg to all checked in today.")
            self.send_aprs_msg(sourcetrunc, "NET [space] msg to checkin & join without notifying everyone.")
            self.send_aprs_msg(sourcetrunc, "LAST/LAST10/LAST15 to retrieve 5,10 or 15 msgs. ?APRST for path.")
            self.send_aprs_msg(sourcetrunc, "SMS [space] 09XXnumber [space] msg to text PHILIPPINE numbers only.")
            self.send_aprs_msg(sourcetrunc, "?APRSM CALLSIGN-SSID(optional) to retrieve last 5 direct msgs.")
            self.send_aprs_msg(sourcetrunc, "LIST to see today's checkins. https://aprsph.net for more info.")


# CQ[space]msg to join,LIST for net,LAST for log. More at aprsph.net.")

# This part is the net checkin. It logs callsigns into a daily list, and it also logs all messages into a cumulative list posted on the web

        elif qry == "ack" and args == "" :
                  logger.info("ACK. Ignoring." )

#This logs messages sent via APRSThursday
        elif qry == "n:hotg" :
           sourcetrunc = source.replace('*','')
# Checking if duplicate message
# If not, write msg to temp file
           dupecheck = qry + " " + args
           if os.path.isfile('/home/pi/ioreth/ioreth/ioreth/lastmsgdirthurs/' + sourcetrunc) and dupecheck == open('/home/pi/ioreth/ioreth/ioreth/lastmsgdirthurs/' + sourcetrunc).read():
                  logger.info("Message is exact duplicate. Stop logging." )
                  return
           else:
                  logger.info("Message is not exact duplicate, now logging" )

                  with open('/home/pi/ioreth/ioreth/ioreth/aprsthursdaytext', 'w') as g:
                       data3 = "{} {}:{} [#APRSThursday]".format(time.strftime("%Y-%m-%d %H:%M:%S %Z"), sourcetrunc, args)
                       g.write(data3)
                       logger.info("Writing %s net message to netlog text", sourcetrunc)
                       fout = open('/home/pi/ioreth/ioreth/ioreth/aprsthursday/index.html', 'a')
                       fout.write(data3)
                       fout.write("\n")
                       fout.close()
                       logger.info("Writing latest checkin message into APRSThursday net log")
#                                                  1234567890123456789012345678901234567890123456789012345678901234567
#                  self.send_aprs_msg(sourcetrunc, "Tnx. Ur msg is also logged at https://aprsph.net -KC8OWL & DU2XXR")
# Record the message somewhere to check if next message is dupe
                  dupecheck = qry + " " + args
                  with open('/home/pi/ioreth/ioreth/ioreth/lastmsgdirthurs/' + sourcetrunc, 'w') as g:
                        lasttext = args
                        g.write(dupecheck)
                        logger.info("Writing %s message somewhere to check for future dupes", sourcetrunc)
                        g.close()




        elif qry == "aprsthursday" :
#                                                   1234567890123456789012345678901234567890123456789012345678901234567
                      self.send_aprs_msg("ANSRVR", "CQ hotg joining #APRSThursday. Also checkin at https://aprsph.net")
                      logger.info("Joining APRSThursday")

        elif qry == "aprstsubs" :
#                                                   1234567890123456789012345678901234567890123456789012345678901234567
                      self.send_aprs_msg("ANSRVR", "j hotg")
                      logger.info("Joining APRSThursday")




        elif qry == "net" or qry == "checking" or qry == "check" or qry == "checkin" or qry == "joining" or qry == "join" or qry == "qrx" or qry == "j"  :
           sourcetrunc = source.replace('*','')
# Checking if duplicate message
# If not, write msg to temp file
           dupecheck = qry + " " + args
           if os.path.isfile('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc) and dupecheck == open('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc).read():
                  logger.info("Message is exact duplicate. Stop logging." )
                  return
           else:
#           if not dupecheck == open('/home/pi/ioreth/ioreth/ioreth/lastmsg').read():
                  logger.info("Message is not exact duplicate, now logging" )

                  with open('/home/pi/ioreth/ioreth/ioreth/nettext', 'w') as g:
                       data3 = "{} {}:{} *".format(time.strftime("%Y-%m-%d %H:%M:%S %Z"), sourcetrunc, args)
                       g.write(data3)
                       logger.info("Writing %s net message to netlog text", sourcetrunc)
                       fout = open('/home/pi/ioreth/ioreth/ioreth/netlog-msg', 'a')
                       fout.write(data3)
                       fout.write("\n")
                       fout.close()
                       logger.info("Writing latest checkin message into cumulative net log")




# Checking if already in log
           with open(filename1, 'r') as file:
                 search_word = sourcetrunc
                 if(search_word in file.read()):
#                                                      1234567890123456789012345678901234567890123456789012345678901234567
                      self.send_aprs_msg(sourcetrunc, "RR new msg.CQ[spc]msg,LIST,LAST,HELP.Net renews @0000Z. aprsph.net")
                      logger.info("Checked if %s already logged to prevent duplicate. Skipping checkin", sourcetrunc)
                      file.close()
# If not in log, then add them
                 else:
                      with open('/home/pi/ioreth/ioreth/ioreth/netlog', 'w') as f:
                         f.write(sourcetrunc)
                         f.close()
                         logger.info("Writing %s checkin to netlog", source)
                      if args == "":
#                                                         1234567890123456789012345678901234567890123456789012345678901234567
                         self.send_aprs_msg(sourcetrunc, "U may also add msg.CQ[spc]msg.LAST for history.LIST for recipients")
#                      else:
#                                                         1234567890123456789012345678901234567890123456789012345678901234567
                      self.send_aprs_msg(sourcetrunc, "RR " + sourcetrunc + ".CQ[spc]msg.LAST view history.LIST for recipients")
                      self.send_aprs_msg(sourcetrunc, "Stdby for CQ msgs. Net renews @0000Z. aprsph.net for info." )
                      logger.info("Replying to %s checkin message", sourcetrunc)

# Record the message somewhere to check if next message is dupe
           dupecheck = qry + " " + args
           with open('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc, 'w') as g:
                lasttext = args
                g.write(dupecheck)
                logger.info("Writing %s message somewhere to check for future dupes", sourcetrunc)
                g.close()

        elif qry == "list" or qry == "?aprsd":
           sourcetrunc = source.replace('*','')
           timestrtxt = time.strftime("%m%d")
           if os.path.isfile(filename1):
                 file = open(filename1, 'r')
                 data21 = file.read()
                 data2 = data21.replace('\n','')
                 file.close()

                 if len(data2) > 310:
                       listbody1 = data2[0:58]
                       listbody2 = data2[58:121]
                       listbody3 = data2[121:184]
                       listbody4 = data2[184:247]
                       listbody5 = data2[247:310]
                       listbody6 = data2[310:]
                       self.send_aprs_msg(sourcetrunc, timestrtxt + " 1/6:" + listbody1 )
                       self.send_aprs_msg(sourcetrunc, "2/6:" + listbody2 )
                       self.send_aprs_msg(sourcetrunc, "3/6:" + listbody3 )
                       self.send_aprs_msg(sourcetrunc, "4/6:" + listbody4 )
                       self.send_aprs_msg(sourcetrunc, "5/6:" + listbody5 )
                       self.send_aprs_msg(sourcetrunc, "6/6:" + listbody6 )
#                       self.send_aprs_msg(sourcetrunc, "CQ[space]text to join & msg all in today's net. Info: aprsph.net" )
#                                                       1234567890123456789012345678901234567890123456789012345678901234567
                       logger.info("Replying with stations heard today. Exceeded length so split into 6: %s", data2 )
                 if len(data2) > 247 and len(data2) <= 310 :
                       listbody1 = data2[0:58]
                       listbody2 = data2[58:121]
                       listbody3 = data2[121:184]
                       listbody4 = data2[184:247]
                       listbody5 = data2[247:310]
                       self.send_aprs_msg(sourcetrunc, timestrtxt + " 1/5:" + listbody1 )
                       self.send_aprs_msg(sourcetrunc, "2/5:" + listbody2 )
                       self.send_aprs_msg(sourcetrunc, "3/5:" + listbody3 )
                       self.send_aprs_msg(sourcetrunc, "4/5:" + listbody4 )
                       self.send_aprs_msg(sourcetrunc, "5/5:" + listbody5 )
#                       self.send_aprs_msg(sourcetrunc, "CQ[space]text to join & msg all in today's net. Info: aprsph.net" )
#                       self.send_aprs_msg(sourcetrunc, "Send CQ +text to msg all in today's log. Info: aprsph.net" )
                       logger.info("Replying with stations heard today. Exceeded length so split into 5: %s", data2 )
                 if len(data2) > 184 and len(data2) <= 247 :
                       listbody1 = data2[0:58]
                       listbody2 = data2[58:121]
                       listbody3 = data2[121:184]
                       listbody4 = data2[184:]
                       self.send_aprs_msg(sourcetrunc, timestrtxt + " 1/4:" + listbody1 )
                       self.send_aprs_msg(sourcetrunc, "2/4:" + listbody2 )
                       self.send_aprs_msg(sourcetrunc, "3/4:" + listbody3 )
                       self.send_aprs_msg(sourcetrunc, "4/4:" + listbody4 )
#                       self.send_aprs_msg(sourcetrunc, "CQ[space]text to join & msg all in today's net. Info: aprsph.net" )
#                       self.send_aprs_msg(sourcetrunc, "Send CQ +text to msg all in today's log. Info: aprsph.net" )
                       logger.info("Replying with stations heard today. Exceeded length so split into 4: %s", data2 )
                 if len(data2) > 121 and len(data2) <= 184:
                       listbody1 = data2[0:58]
                       listbody2 = data2[58:121]
                       listbody3 = data2[121:]
                       self.send_aprs_msg(sourcetrunc, timestrtxt + " 1/3:" + listbody1 )
                       self.send_aprs_msg(sourcetrunc, "2/3:" + listbody2 )
                       self.send_aprs_msg(sourcetrunc, "3/3:" + listbody3 )
#                       self.send_aprs_msg(sourcetrunc, "CQ[space]text to join & msg all in today's net. Info: aprsph.net" )
#                       self.send_aprs_msg(source, "Send CQ +text to msg all in today's log. Info: aprsph.net" )
                       logger.info("Replying with stations heard today. Exceeded length so split into 3: %s", data2 )
                 if len(data2) > 58 and len(data2) <= 121:
                       listbody1 = data2[0:58]
                       listbody2 = data2[58:]
                       self.send_aprs_msg(sourcetrunc, timestrtxt + " 1/2:" + listbody1 )
                       self.send_aprs_msg(sourcetrunc, "2/2:" + listbody2 )
#                       self.send_aprs_msg(sourcetrunc, "CQ[space]text to join & msg all in today's net. Info: aprsph.net" )
#                       self.send_aprs_msg(sourcetrunc, "Send CQ +text to msg all in today's log. Info: aprsph.net" )
                       logger.info("Replying with stations heard today. Exceeded length so split into 2: %s", data2 )
                 if len(data2) <= 58:
                       self.send_aprs_msg(sourcetrunc, timestrtxt + ":" + data2 )
#                       self.send_aprs_msg(sourcetrunc, "CQ[space]text to join & msg all in today's net. Info: aprsph.net" )
#                       self.send_aprs_msg(sourcetrunc, "Send CQ +text to msg all in today's log. Info: aprsph.net" )
                       logger.info("Replying with stations heard today: %s", data2 )
#                                                 1234567890123456789012345678901234567890123456789012345678901234567
                 self.send_aprs_msg(sourcetrunc, "CQ[space]msg to join/chat. LAST for msg log. Info: aprsph.net" )
           else:
                 self.send_aprs_msg(sourcetrunc, "No stations checked in yet. CQ[space]msg to checkin.") 

        elif qry == "cq" or qry == "hi" or qry == "hello" or qry == "happy" or qry == "ga" or qry == "gm" or qry == "ge" or qry == "gn" or qry == "good" or qry == "ok" or qry == "k"  :

           sourcetrunc = source.replace('*','')
           cqnet = 0
           nocheckins = 0
# Checking if duplicate message
           dupecheck = qry + " " + args
           if os.path.isfile('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc) and dupecheck == open('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc).read():
                  logger.info("Message is exact duplicate, stop logging." )
                  return
           else:
                  logger.info("Message is not exact duplicate, now logging" )
# This logs the message into net text draft for adding into the message log.
                  with open('/home/pi/ioreth/ioreth/ioreth/nettext', 'w') as cqm:
                       if qry == "cq" :
                          data9 = "{} {}:{}".format(time.strftime("%Y-%m-%d %H:%M:%S %Z"), sourcetrunc, args)
                       else :
                          data9 = "{} {}:{} {}".format(time.strftime("%Y-%m-%d %H:%M:%S %Z"), sourcetrunc, qry, args)
                       cqm.write(data9)
                       cqm.close()
                       logger.info("Writing %s CQ message to nettext", sourcetrunc)
                       fout = open('/home/pi/ioreth/ioreth/ioreth/netlog-msg', 'a')
                       fout.write(data9)
                       fout.write("\n")
                       fout.close()
                       logger.info("Writing latest checkin message into cumulative net log")

# If no checkins, we will check you in and also post your CQ message into the CQ log, and also include in net log
           if not os.path.isfile(filename3) :
               nocheckins = 1
               self.send_aprs_msg(sourcetrunc, "You are first in today's log." ) 
               with open('/home/pi/ioreth/ioreth/ioreth/netlog', 'w') as nt:
                   nt.write(sourcetrunc)
                   logger.info("Writing %S message to netlog", sourcetrunc)
# Checking if duplicate message
               dupecheck = qry + " " + args
               if os.path.isfile('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc) and dupecheck == open('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc).read():
                   logger.info("Message is exact duplicate, stop logging" )
                   return
               else:
                   logger.info("Message is not exact duplicate, now logging" )
                   with open('/home/pi/ioreth/ioreth/ioreth/nettext', 'w') as ntg:
# If not duplicate, this logs the message into net text draft for adding into the message log.

                        if qry == "cq" :
                           data3 = "{} {}:{}".format(time.strftime("%Y-%m-%d %H:%M:%S %Z"), sourcetrunc, args)
                        else :
                           data3 = "{} {}:{} {}".format(time.strftime("%Y-%m-%d %H:%M:%S %Z"), sourcetrunc, qry, args)
                        ntg.write(data3)
                        logger.info("Writing %s net message to netlog-msg", sourcetrunc)
                        fout = open('/home/pi/ioreth/ioreth/ioreth/netlog-msg', 'a')
                        fout.write(data3)
                        fout.write("\n")
                        fout.close()
                        logger.info("Writing latest checkin message into cumulative net log")

               logger.info("Advising %s to checkin", sourcetrunc)
               return
# If not yet in log, add them in and add their message to net log.
           file = open(filename1, 'r')
           search_word = sourcetrunc
           if not (search_word in file.read()):
                with open('/home/pi/ioreth/ioreth/ioreth/netlog', 'w') as cqf:
                      cqf.write(sourcetrunc)
                      logger.info("CQ source not yet in net. Writing %s checkin to netlog", source)

# Deprecated this part of the net, since CQs now default to the "Net" portion of the checkin (we have unified
# the checkin between CQ and Net). Perhaps we shall use another keyword for that purpose, since most people are
# Doing a Net and then a CQ afterward.
#                with open('/home/pi/ioreth/ioreth/ioreth/nettext', 'w') as ntg:
#                      if qry == "cq" :
#                         data3 = "{} {}:{}".format(time.strftime("%Y-%m-%d %H:%M:%S %Z"), sourcetrunc, args)
#                      else :
#                         data3 = "{} {}:{} {}".format(time.strftime("%Y-%m-%d %H:%M:%S %Z"), sourcetrunc, qry, args)
#                      ntg.write(data3)
                      cqnet = 1
#                      logger.info("Writing %s net message to netlog-msg", sourcetrunc)
# Record the message somewhere to check if next message is dupe
           with open('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc, 'w') as g:
                dupecheck = qry + " " + args
                g.write(dupecheck)
                logger.info("Writing %s message somewhere to check for future dupes", sourcetrunc)

# Send the message to all on the QRX list for today
           lines = []
           sourcetrunc = source.replace('*','')
           with open(filename3) as sendlist:
                lines = sendlist.readlines()
           count = 0
           for line in lines:
                linetrunc = line.replace('\n','')
                count += 1
                strcount = str(count)
                msgbodycq = sourcetrunc + ":" + args
                msgbody = sourcetrunc + ":" + qry + " " + args
                if not sourcetrunc == linetrunc:
                      if qry == "cq" :
                         if len(msgbodycq) > 67 :
                            msgbody1 = msgbodycq[0:61]
                            msgbody2 = msgbodycq[61:]
                            self.send_aprs_msg(linetrunc, msgbody1 + "+" )
                            self.send_aprs_msg(linetrunc, msgbody2 )
                         else:
                            self.send_aprs_msg(linetrunc, msgbodycq )
#                         self.send_aprs_msg(linetrunc, sourcetrunc + ":" + args)
                      else :
                         if len(msgbody) > 67 :
                            msgbody1 = msgbody[0:61]
                            msgbody2 = msgbody[61:]
                            self.send_aprs_msg(linetrunc, msgbody1 + "+" )
                            self.send_aprs_msg(linetrunc, msgbody2 )
                         else:
                            self.send_aprs_msg(linetrunc, msgbody )


#                         self.send_aprs_msg(linetrunc, sourcetrunc + ":" + qry + " " + args)
#                                                    1234567890123456789012345678901234567890123456789012345678901234567
                      self.send_aprs_msg(linetrunc, "CQ [space] msg to reply.LIST for recipients.LAST/LAST10 for history" )
                logger.info("Sending CQ message to %s except %s", linetrunc, sourcetrunc)
# This reads the day's log from a line-separated list for processing one message at a time.
# Advise sender their message is being processed/sent
           daylog = open(filename1, 'r')
           dayta2 = daylog.read() 
           daylog.close()
           dayta31 = dayta2.replace(sourcetrunc + ',','')
           dayta3 = dayta31.replace('\n','')
#           dayta3count = dayta3.count(",")
           if nocheckins == 1:
                 self.send_aprs_msg(sourcetrunc, "No CQ recipients yet. You are first in today's log." ) 
           else:
               if len(dayta3) > 63:
                     count = 0
                     for i in dayta3:
                         if i == ',':
                            count = count + 1
                     self.send_aprs_msg(sourcetrunc, "QSP " + str(count) + " stations. LIST to view recipients." )
               elif len(dayta3) < 1:
                     self.send_aprs_msg(sourcetrunc, "No other checkins yet. You are first in today's log." + dayta3 )
               else:
                     self.send_aprs_msg(sourcetrunc, "QSP " + dayta3 )
           logger.info("Advising %s of messages sent to %s", sourcetrunc, dayta3)
           if cqnet == 1:
                 self.send_aprs_msg(sourcetrunc, "Ur also checked in! Stby for mesgs. Net resets 0000Z. aprsph.net" )
                 logger.info("Adivising %s they are also now checked in.", sourcetrunc)

# START ?APRSM or MESSAGE retrieval from aprs.fi. This feature uses the API to retrieve the last 10 messages and delivers to the user.
# May be useful for checking for any missed messages.

# First we test the output file
        elif qry == "?aprsm" or qry == "msg" or qry == "m" or qry == "msg10" or qry == "m10" :
           sourcetrunc = source.replace('*','')
           if args == "" :
                callsign = sourcetrunc.upper()
           else:
                callsign = args.split(' ', 1)[0].upper()
           apicall = "https://api.aprs.fi/api/get?what=msg&dst=" + callsign + "&apikey=[YOUR API KEY HERE]&format=json"
#           jsonoutput = "/home/pi/ioreth/ioreth/ioreth/aprsm/" + sourcetrunc + ".json"
#           msgoutput = "/home/pi/ioreth/ioreth/ioreth/aprsm/" + sourcetrunc + ".txt"
#           cmd = "wget \"" + apicall + "\" -O " + jsonoutput
           try:
#               hdr = { 'User-Agent' : 'Ioreth APRSPH bot (aprsph.net)' }
#               req = urllib.request.Request(apicall, headers=hdr, timeout=2)
#               response = urllib.request.urlopen(req).read().decode('UTF-8')
#               hdr = "'user-agent': 'APRSPH/2023-01-28b (+https://aprsph.net)'"
               hdr = { 'User-Agent': 'Ioreth APRSPH bot (https://aprsph.net)' }
#               response = urllib.request.urlopen(apicall, timeout=2).read().decode('UTF-8')
               req = urllib.request.Request(url=apicall, headers={'User-Agent':' APRSPH/2023-01-29 (+https://aprsph.net)'})
# Mozilla/5.0 (Windows NT 6.1; WOW64; rv:12.0) Gecko/20100101 Firefox/12.0'})
               response = urllib.request.urlopen(req, timeout=2).read().decode('UTF-8')
#               response = urllib.request.urlopen(apicall, timeout=2).read().decode('UTF-8')
#               response.add_header('User-Agent','APRSPH/2023-01-28 (+https://aprsph.net)')
               jsonResponse = json.loads(response)
           except:
               self.send_aprs_msg(sourcetrunc, "Error in internet or connection to aprs.fi.")
#               logger.info("%s", response)
#               logger.info("%s", jsonResponse)

               logger.info("Internet error in retrieving messages for %s", callsign)
               return

           if jsonResponse['found'] == 0:
                   self.send_aprs_msg(sourcetrunc, "No recent msgs for " + callsign + " or old data was purged.")
                   logger.info("No messages retrieved for %s", callsign)
                   return
           else:
#                   logger.info("%s", response)
#                   logger.info("%s", jsonResponse)
                   self.send_aprs_msg(sourcetrunc, "Recent messages to " + callsign + " retrieved from aprs.fi." )

                   count = 0
                   for rows in jsonResponse['entries']:
#                         logger.info("%s", rows)
                         if count == 5 and qry == "m" or qry == "msg" or qry == "?aprsm" :
                            break
                         count += 1
                         msgtime = datetime.datetime.fromtimestamp(int(rows['time'])).strftime('%m-%d %H%MZ')
                         msgsender = rows['srccall']
                         msgmsg = rows['message']
                         strcount = str(count)
                         msgbody = strcount + "." + msgtime + " " + msgsender + ":" + msgmsg
                         if len(msgbody) > 67 :
                            msgbody1 = msgbody[0:61]
                            msgbody2 = msgbody[61:]
                            self.send_aprs_msg(sourcetrunc, msgbody1 + "+" )
                            self.send_aprs_msg(sourcetrunc, strcount + ".+" + msgbody2 )
                         else:
                            self.send_aprs_msg(sourcetrunc, msgbody )

#                         self.send_aprs_msg(sourcetrunc, str(count) + ".From " + msgsender + " sent on " + msgtime )
#                         self.send_aprs_msg(sourcetrunc, str(count) + "." + msgmsg )
                   logger.info("Sending last messages retrieved for %s", callsign)

#                msgfile.write("\n")

# START ERIC
# This below is an experimental feature for incident command. It's based on the CQ portion of the code, but basically does these:
# 1. Adds the message to an incident command draft.
# 2. Lets the sender add more messages to the draft.
# 3. Lets the sender push the message to a web log.
# 4. Sends the message to stations identified as incident commanders


        elif qry == "ichelp" :
           sourcetrunc = source.replace('*','')
           self.send_aprs_msg(sourcetrunc, "IC[space]msg to start report.ICLAST,ICLATEST for last reports.")
           logger.info("Sending IC help message to %s", sourcetrunc)

        elif qry == "ic" :
           sourcetrunc = source.replace('*','')
           cqnet = 0
# Checking if duplicate message
           dupecheck = qry + " " + args
           if os.path.isfile('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc) and dupecheck == open('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc).read():
                  logger.info("Message is exact duplicate, stop logging" )
                  return
           else:
                  logger.info("Message is not exact duplicate, now logging" )
                  icdraft = '/home/pi/ioreth/ioreth/ioreth/eric/draft/' + sourcetrunc
                  if not os.path.isfile(icdraft):
                       draftmsg = open(icdraft, 'w')
                       with open(icdraft, 'a') as draftmsg:
                         data8 = "Incident Report from {} started on {}\n".format(sourcetrunc,time.strftime("%Y-%m-%d %H:%M:%S %Z"))
                         draftmsg.write(data8)
#                         data9 = "{}:{}\n".format(time.strftime("%H:%M:%S"), args)
#                         draftmsg.write(data9)
                         logger.info("Created and writing %s draft IC file", sourcetrunc)
                  with open(icdraft, 'a') as cqm:
                         data9 = "{}:{}\n".format(time.strftime("%H:%M:%S"), args)
#                         data9 = "{}\n".args
                         cqm.write(data9)
                         logger.info("Writing %s IC message to eric", sourcetrunc)
                         cqm.close

# Record the message somewhere to check if next message is dupe
           with open('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc, 'w') as g:
                dupecheck = qry + " " + args
#                lasttext = args
                g.write(dupecheck)
                logger.info("Writing %s message somewhere to check for future dupes", sourcetrunc)

# Advise sender their message is logged
           self.send_aprs_msg(sourcetrunc, "RR:" + args[0:24] + ".IC[spc]msg to add.ICPUB to post or ICANCEL.")
           logger.info("Advising %s of message %s being logged", sourcetrunc, args)

# This part lets us push to the web.

        elif qry == "icancel":
           sourcetrunc = source.replace('*','')
           icdraft = '/home/pi/ioreth/ioreth/ioreth/eric/draft/' + sourcetrunc
           if os.path.isfile(icdraft):
              os.remove(icdraft)
              self.send_aprs_msg(sourcetrunc, "Report deleted. IC [space] msg to start new.")
           if not os.path.isfile(icdraft):
              self.send_aprs_msg(sourcetrunc, "No report to delete. IC [space] msg to start new.")

        elif qry == "icpub":
           sourcetrunc = source.replace('*','')
           icdraft = '/home/pi/ioreth/ioreth/ioreth/eric/draft/' + sourcetrunc
           if not os.path.isfile(icdraft):
              self.send_aprs_msg(sourcetrunc, "No report to publish. IC [space] msg to start new.")
           if os.path.isfile(icdraft):
              file = open(icdraft, 'r')
              readdraft = file.read()
              file.close()
              fout = open(iclog, 'a')
              fout.write(readdraft)
              repsubmitted = "Incident Report submitted by {} on {}".format(sourcetrunc, time.strftime("%Y-%m-%d %H:%M:%S %Z"))
              fout.write(repsubmitted)
              fout.write("\n\n")
              fout.close()
              logger.info("Copying report from %s into the main IC log.", sourcetrunc)
              iclasts = iclast + "/" + sourcetrunc
              flast = open(iclasts, 'w')
              flast.write(readdraft)
              flast.write(repsubmitted)
#              flast.write("\n\n")
              flast.close()
              copylatest = "cp " + iclasts + " " + iclatest
              os.system(copylatest)
              os.remove(icdraft)
              logger.info("Copied draft to iclatest and deleting draft report from %s", sourcetrunc)
              cmd = 'scp /home/pi/ioreth/ioreth/ioreth/eric/eric [DESTINATION HERE]'
              try:
                 os.system(cmd)
                 logger.info("Uploading iclog to the web")
                 self.send_aprs_msg(sourcetrunc, "Published the log messages to web.")
              except:
                 logger.info("ERROR uloading iclog to the web")
                 self.send_aprs_msg(sourcetrunc, "Error in publishing the log messages to web.")
# Send the message to all on the IC list.
              lines = []
              sourcetrunc = source.replace('*','')
              with open(iclist) as sendlist:
                 lines = sendlist.readlines()
              count = 0
              for line in lines:
                 linetrunc = line.replace('\n','')
                 count += 1
                 with open(iclasts) as sendlast:
                     lineslast = sendlast.readlines()
                 countlast = 0
                 for linelast in lineslast:
                     countlast += 1
                     linelasttrunc = linelast.replace('\n','')
                     self.send_aprs_msg(linetrunc,linelasttrunc[9:])
              logger.info("Sending IC message to %s", linelasttrunc)
# We will attempt to send an email
              lines = []
              with open(iclasts) as reportsubject:
                  reportsubj = reportsubject.readlines()[-1]
              icmailcmd = "cat " + iclasts + " | /home/pi/ioreth/ioreth/ioreth/eric/patmail.sh [YOUR EMAIL] \"" + reportsubj + "\" telnet" 
              try:
                  os.system(icmailcmd)
                  self.send_aprs_msg(sourcetrunc, "Emailed " + reportsubj[9:])
                  logger.info("Sending IC message to email") 
              except:
                  self.send_aprs_msg(sourcetrunc, "IC email error.")
                  logger.info("Error sending IC message to email") 

# For below, just email and not send/publish to all
        elif qry == "icmail":
              iclasts = iclast + "/" + sourcetrunc
              lines = []
              if not os.path.isfile(iclasts):
                  self.send_aprs_msg(sourcetrunc, "No report to email. IC [space] message to start new report.")
                  logger.info("No report to email") 
                  return
              with open(iclasts) as reportsubject:
                  reportsubj = reportsubject.readlines()[-1]
              icmailcmd = "cat " + iclasts + " | /home/pi/ioreth/ioreth/ioreth/eric/patmail.sh [YOUR EMAIL] \"" + reportsubj + "\" telnet" 
              try:
                  os.system(icmailcmd)
                  self.send_aprs_msg(sourcetrunc, "Emailed " + reportsubj[9:])
                  logger.info("Sending IC message to email") 
              except:
                  self.send_aprs_msg(sourcetrunc, "IC email error.")
                  logger.info("Error sending IC message to email") 




        elif qry == "iclast":
# Retrieve the last report
              lineslast = []
              sourcetrunc = source.replace('*','')
              iclasts = iclast + "/" + sourcetrunc
              if not os.path.isfile(iclasts):
                  self.send_aprs_msg(sourcetrunc,"No report to retrieve for " + sourcetrunc)
                  logger.info("No IC report to retrieve for %s.", sourcetrunc)
                  return
              with open(iclasts) as sendlast:
                  lineslast = sendlast.readlines()
              countlast = 0
              for linelast in lineslast:
                  countlast += 1
                  linelasttrunc = linelast.replace('\n','')
                  self.send_aprs_msg(sourcetrunc,str(countlast) + "." + linelasttrunc[9:])
              logger.info("Sending lst IC report to %s.", sourcetrunc)

        elif qry == "iclatest":
# Retrieve the last report from anyone
              lineslast = []
              sourcetrunc = source.replace('*','')
              with open(iclatest) as sendlast:
                  lineslast = sendlast.readlines()
              countlast = 0
              for linelast in lineslast:
                  countlast += 1
                  linelasttrunc = linelast.replace('\n','')
                  self.send_aprs_msg(sourcetrunc,str(countlast) + "." + linelasttrunc[9:])
              logger.info("Sending latest IC report to %s.", sourcetrunc)




# This part allows user to retrieve the IC log

        elif qry == "iclog":
             with open(iclog) as netlast:
                  lasts = netlast.readlines()
                  lastlines = lasts[-10:]
                  netlast.close()
             count = 0
             for line in lastlines:
                  count += 1
                  self.send_aprs_msg(sourcetrunc, str(count) + "." + line[9:] )
             logger.info("Sending last 10 IC messages to  %s", sourcetrunc)
             self.send_aprs_msg(sourcetrunc, "Last 10 IC messages received.")

        elif qry == "iclog2":
             with open(iclog) as netlast:
                  lasts = netlast.readlines()
                  lastlines = lasts[-21:-11]
                  netlast.close()
             count = 0
             for line in lastlines:
                  count += 1
                  self.send_aprs_msg(sourcetrunc, str(count) + "." + line[9:] )
             logger.info("Sending 10 out of last 20 IC messages to  %s", sourcetrunc)
             self.send_aprs_msg(sourcetrunc, "10 of last 20 IC mesge received.")

        elif qry == "iclog3":
             with open(iclog) as netlast:
                  lasts = netlast.readlines()
                  lastlines = lasts[-31:-21]
                  netlast.close()
             count = 0
             for line in lastlines:
                  count += 1
                  self.send_aprs_msg(sourcetrunc, str(count) + "." + line[9:] )
             logger.info("Sending 10 out of last 30 IC messages to  %s", sourcetrunc)
             self.send_aprs_msg(sourcetrunc, "10 of last 30 IC mesge received.")


# END ERIC




# This is for permanent subscribers in your QST list. 
# Basically a fixed implementation of "CQ" but with subscribers not having any control.
# Good for tactical uses, such as RF-only or off-grid environments.

        elif qry == "qst":
             sourcetrunc = source.replace('*','')
             lines = []
             with open(dusubs) as f:
                  lines = f.readlines()
             count = 0
             for line in lines:
                  count += 1
#                  mespre = (line[1:4])
                  self.send_aprs_msg(line.replace('\n',''), sourcetrunc + "/" + args )
                  logger.info("Sending QST message to %s", line)
             file = open(dusubslist, 'r')
             data21 = file.read()  
             data2 = data21.replace('\n','')
             file.close()
             self.send_aprs_msg(source, "Sent msg to QST recipients. Ask DU2XXR for list." )
             logger.info("Advising %s of messages sent to %s", sourcetrunc, data2)
#             file.close()

# Lines below let the user retrieve the last messages from the log.
        elif qry == "last" or qry == "log" or qry == "last5" : 
             with open(filename2) as netlast:
                  lasts = netlast.readlines()
                  lastlines = lasts[-5:]
                  netlast.close()
#                                             1234567890123456789012345678901234567890123456789012345678901234567
             self.send_aprs_msg(sourcetrunc, "CQ[space]msg reply,LIST for recipients,HELP cmds. Info:aprsph.net" )
             count = 0
             for line in lastlines:
                  count += 1
                  strcount = str(count)
                  msgbody = str(count) + "." + line[24:]
                  if len(msgbody) > 67 :
                       msgbody1 = msgbody[0:61]
                       msgbody2 = msgbody[61:]
                       self.send_aprs_msg(sourcetrunc, msgbody1 + "+" )
                       self.send_aprs_msg(sourcetrunc, strcount + ".+" + msgbody2 )
                  else:
                       self.send_aprs_msg(sourcetrunc, msgbody )

#                  if len(msgbody) < 67
#                     self.send_aprs_msg(sourcetrunc, msgbody)
#                  else:
#                     self.send_aprs_msg(sourcetrunc, msgbody[0:67])
#                     self.send_aprs_msg(sourcetrunc, msgbody)

#                  self.send_aprs_msg(sourcetrunc, str(count) + "." + line[24:91] )
             logger.info("Sending last 5 cqlog messages to  %s", sourcetrunc)

        elif qry == "last10" or qry == "log10" : 
             with open(filename2) as netlast:
                  lasts = netlast.readlines()
                  lastlines = lasts[-10:]
                  netlast.close()
#             self.send_aprs_msg(sourcetrunc, "CQ[space]msg to reply,LIST for QRX,HELP for cmds. Info: aprsph.net" )
             self.send_aprs_msg(sourcetrunc, "CQ[space]msg reply,LIST for recipients,HELP cmds. Info:aprsph.net" )
#             self.send_aprs_msg(sourcetrunc, "Last 10 mesgs. CQ[space]text to reply,LIST for QRX,HELP for cmds." )
#             self.send_aprs_msg(sourcetrunc, "Last 10 CQ msgs sent. CQ +text to reply,LIST for QRX,HELP for cmds." )
             count = 0
             for line in lastlines:
                  count += 1
                  strcount = str(count)
                  msgbody = str(count) + "." + line[24:]
                  if len(msgbody) > 67 :
                       msgbody1 = msgbody[0:61]
                       msgbody2 = msgbody[61:]
                       self.send_aprs_msg(sourcetrunc, msgbody1 + "+" )
                       self.send_aprs_msg(sourcetrunc, strcount + ".+" + msgbody2 )
                  else:
                       self.send_aprs_msg(sourcetrunc, msgbody )


#                  self.send_aprs_msg(sourcetrunc, str(count) + "." + line[24:91] )
             logger.info("Sending last 10 cqlog messages to  %s", sourcetrunc)

        elif qry == "last15" or qry == "log15" : 
             with open(filename2) as netlast:
                  lasts = netlast.readlines()
                  lastlines = lasts[-15:]
                  netlast.close()
             self.send_aprs_msg(sourcetrunc, "CQ[space]msg reply,LIST for recipients,HELP cmds. Info:aprsph.net" )
#             self.send_aprs_msg(sourcetrunc, "CQ[space]msg to reply,LIST for QRX,HELP for cmds. Info: aprsph.net" )
#             self.send_aprs_msg(sourcetrunc, "Last 15 mesgs. CQ[space]text to reply,LIST for QRX,HELP for cmds." )
#             self.send_aprs_msg(sourcetrunc, "Last 10 CQ msgs sent. CQ +text to reply,LIST for QRX,HELP for cmds." )
             count = 0
             for line in lastlines:
                  count += 1
                  strcount = str(count)
                  msgbody = str(count) + "." + line[24:]
                  if len(msgbody) > 67 :
                       msgbody1 = msgbody[0:61]
                       msgbody2 = msgbody[61:]
                       self.send_aprs_msg(sourcetrunc, msgbody1 + "+" )
                       self.send_aprs_msg(sourcetrunc, strcount + ".+" + msgbody2 )
                  else:
                       self.send_aprs_msg(sourcetrunc, msgbody )



#                  count += 1
#                  self.send_aprs_msg(sourcetrunc, str(count) + "." + line[24:91] )
             logger.info("Sending last 15 cqlog messages to  %s", sourcetrunc)


# Let users set up SMS aliases. Be sure to create the paths yourself if not yet existent.
        elif qry == "smsalias" or qry == "setalias":
             sourcetrunc = source.replace('*','')
             callnossid = sourcetrunc.split('-', 1)[0]
             SMS_DESTINATION = args[0:11]
             SMS_ALIAS = args[12:]
             aliasscratch = "/home/pi/ioreth/ioreth/ioreth/smsaliasscratch/" + callnossid
             aliasfile = "/home/pi/ioreth/ioreth/ioreth/smsalias/" + callnossid
# stop processing duplicates, since APRS sends messages multiple times.
             if not os.path.isfile(aliasscratch):
                 aliases = open(aliasscratch, 'w')
             if args == open(aliasscratch).read():
                 logger.info("Already processed alias for %s %s recently. No longer processing.", SMS_DESTINATION, SMS_ALIAS)
                 return
             if not args[0:2] == "09":
                 self.send_aprs_msg(sourcetrunc, "SMSALIAS 09XXXXXXXXX name to set. SMS NAME to send thereafter.")
                 return
             if not os.path.isfile(aliasscratch):
                 aliases = open(aliasscratch, 'w')
             with open(aliasscratch, 'w') as makealias:
                 writealias = "{} {}".format(SMS_DESTINATION, SMS_ALIAS)
                 makealias.write(writealias)
             if not os.path.isfile(aliasfile):
                 aliases = open(aliasfile, 'a')
             with open(aliasfile, 'a') as makealias:
                 writealias = "{} {}\n".format(SMS_DESTINATION, SMS_ALIAS)
                 makealias.write(writealias)
                 self.send_aprs_msg(sourcetrunc, "SMS " + SMS_ALIAS + " will now send to " + SMS_DESTINATION)
                 logger.info("Writing alias for sender %s as %s %s", sourcetrunc, SMS_DESTINATION, SMS_ALIAS)

# SMS handling for DU recipients. Note that this requires gammu-smsd daemon running on your local machine, with
# the user having access to the SMS storage directories, as well as an extra folder called "processed" where
# SMS inbox messages are moved once they are processed.
        elif qry == "sms":
          sourcetrunc = source.replace('*','')
          callnossid = sourcetrunc.split('-', 1)[0]
          SMS_TEXT = ("APRS msg fr " + sourcetrunc + " via APRSPH:\n\n" + args.split(' ', 1)[1] + "\n\n@" + sourcetrunc + " [space] msg to reply. APRS msgs are NOT private!" )
# First set the characters after SMS as the initial destination
          SMS_DESTINATION = ""
#          SMS_DESTINATION = args[0:11]
# First check if using alias or not
          aliasfound = []
          aliasfile = "/home/pi/ioreth/ioreth/ioreth/smsalias/" + callnossid
          cellaliasfile = "/home/pi/ioreth/ioreth/ioreth/smsalias/CELLULAR"
          smsoralias = args.split(' ', 1)[0]
          smsoraliasupper = smsoralias.upper()
# Check cellular-initiated aliases first
          with open(cellaliasfile, 'r') as file:
               lines = file.readlines()
          count = 0
          for line in lines:
                          count += 1
                          names = line.replace('\n','')
                          names2 = names[12:]
                          logger.info("Trying to match '%s' with '%s'.", smsoralias, names2.upper() )
                          if smsoraliasupper == names2.upper():
                             SMS_DESTINATION = line[0:11]
                             logger.info("Self-set alias found for %s as %s.", smsoralias, SMS_DESTINATION )

# If Alias file is present, then APRS-initiated alias takes precedence

          if os.path.isfile(aliasfile):
#                SMS_DESTINATION = args[0:11]
#                logger.info("No alias file found, just sending to number." )
#          else:






              logger.info("Callsign's own alias file found, trying to match '%s' to a number.",smsoralias )
              lines = []
              with open(aliasfile, 'r') as file:
                    lines = file.readlines()
              count = 0
              for line in lines:
                          count += 1
                          names = line.replace('\n','')
                          names2 = names[12:]
                          logger.info("Trying to match '%s' with '%s'.", smsoralias, names2.upper() )
                          if smsoraliasupper == names2.upper():
                             SMS_DESTINATION = line[0:11]
                             logger.info("Alias found for %s as %s.", smsoralias, SMS_DESTINATION )

          if SMS_DESTINATION == "":
                SMS_DESTINATION = args[0:11]
                logger.info("No alias file found, just sending to number." )

# establish our SMS message

          sendsms = ( "echo '" + SMS_TEXT + "' | gammu-smsd-inject TEXT " + SMS_DESTINATION )

# Check first if duplicate
          dupecheck = qry + " " + args

          if os.path.isfile('/home/pi/ioreth/ioreth/ioreth/lastmsgsms/' + sourcetrunc) and  dupecheck == open('/home/pi/ioreth/ioreth/ioreth/lastmsgsms/' + sourcetrunc).read():
             logger.info("Received message for SMS that is exact duplicate. Stop sending SMS." )
             return
          else:
             logger.info("Received message for SMS that is not exact duplicate, now sending SMS" )

             if args == "":
                 self.send_aprs_msg(sourcetrunc, "SMS 09XXXXXXXXX msg. PH#s only. SMSALIAS # name to set nicknames." )
                 logger.info("Replying to %s about SMS instructions", sourcetrunc)
                 return


             with open('/home/pi/ioreth/ioreth/ioreth/lastmsgsms/' + sourcetrunc, 'w') as g:
#                   lasttext = args
                   g.write(dupecheck)
                   logger.info("Writing %s message somewhere to check for future dupes", sourcetrunc)
             sourcetrunc = source.replace('*','')

# Validating the destination. In the Philippines, cell numbers start with 09XX. Adjust this accordingly.

             if not SMS_DESTINATION[0:2] == "09":
                 self.send_aprs_msg(sourcetrunc, "Num or SMSALIAS invalid. Usage:SMS 09XXXXXXXXX or alias msg. PH# only" )
                 logger.info("Replying to %s that %s is not a valid number.", sourcetrunc, SMS_DESTINATION)
                 return

             try:
#                   os.system(sendsms)
                   self.send_aprs_msg(sourcetrunc, "SMS " + smsoralias +" -sending. Note: APRS msgs not private." )
                   aliasfile = "/home/pi/ioreth/ioreth/ioreth/smsalias/" + callnossid
                   smsoralias = args.split(' ', 1)[0]
                   if not os.path.isfile(aliasfile):
                         self.send_aprs_msg(sourcetrunc, "U may use alias.SMSALIAS 09XXXXXXXXX NAME to set.SMS NAME to send.")
                   logger.info("Replying to %s that SMS to %s is being sent", sourcetrunc, SMS_DESTINATION)
                   os.system(sendsms)
                   logger.info("Sending SMS from %s to %s", sourcetrunc, SMS_DESTINATION)
             except:
                   self.send_aprs_msg(sourcetrunc, 'SMS Could not be sent')
                   logger.info("Could not send SMS from %s to %s", sourcetrunc, SMS_DESTINATION)

# This is necessary, since APRS messages may be sent or received multiple times (e.g., heard from another digipeater)
# This ensures that the SMS being sent will not be doubled. When the same message is heared on this machine, processing
# Stops already because the message has been queued by Gammu-smsd. Same case with other processes here.

#          else:
#             logger.info("SMS fromm %s to %s is a duplicate. No longer processing", sourcetrunc, SMS_DESTINATION)

        elif qry in random_replies:
            self.send_aprs_msg(sourcetrunc, random_replies[qry] )

        else:
#                                            1234567890123456789012345678901234567890123456789012345678901234567
            self.send_aprs_msg(sourcetrunc, "ERROR:CQ[space]msg to join,LIST to view,HELP or aprsph.net for info" )
            dupecheck = qry + " " + args
            with open('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc, 'w') as g:
                lasttext = args
                g.write(dupecheck)
                logger.info("Writing %s message somewhere to check for future dupes", sourcetrunc)

    def send_aprs_msg(self, to_call, text):
        self._client.enqueue_frame(self.make_aprs_msg(to_call, text))

    def send_aprs_status(self, status):
        self._client.enqueue_frame(self.make_aprs_status(status))


class SystemStatusCommand(remotecmd.BaseRemoteCommand):
    def __init__(self, cfg):
        remotecmd.BaseRemoteCommand.__init__(self, "system-status")
        self._cfg = cfg
        self.status_str = ""

    def run(self):
# These lines count the number of SMS sent and received
        smsproc = "ls -1 /var/spool/gammu/processed | wc -l > /home/pi/ioreth/ioreth/ioreth/smsrxcount"
        smsrxcount = os.system(smsproc)
        smssent = "ls -1 /var/spool/gammu/sent | wc -l > /home/pi/ioreth/ioreth/ioreth/smstxcount"
        smstxcount = os.system(smssent)
        

        smsrxnum = open('/home/pi/ioreth/ioreth/ioreth/smsrxcount', 'r')
        smsrxcounts = smsrxnum.read()
#        smsrxtotals1 = smsrxcounts.replace('total ','')
        smsrxtotals = smsrxcounts.replace('\n','')
        smsrxnum.close()

        smstxnum = open('/home/pi/ioreth/ioreth/ioreth/smstxcount', 'r')
        smstxcounts = smstxnum.read()
#        smstxtotals1 = smstxcounts.replace('total ','')
        smstxtotals = smstxcounts.replace('\n','')
        smstxnum.close()

        net_status = (
            self._check_host_scope("Link", "eth_host")
            + self._check_host_scope("YSF", "inet_host")
            + self._check_host_scope("VHF", "dns_host")
            + self._check_host_scope("VPN", "vpn_host")
        )
        self.status_str = "NET to checkin.HELP 4 cmds.SMS R%s T%s DU2XXR" % (
#            time.strftime("%Y-%m-%d %H:%M:%S %Z"),
            smsrxtotals,
            smstxtotals,
#            utils.human_time_interval(utils.get_uptime()),
        )
        if len(net_status) > 0:
            self.status_str += "," + net_status

    def _check_host_scope(self, label, cfg_key):
        if not cfg_key in self._cfg:
            return ""
        ret = utils.simple_ping(self._cfg[cfg_key])
        return " " + label + (":Ok" if ret else ":Err")


class ReplyBot(AprsClient):
    def __init__(self, config_file):
        AprsClient.__init__(self)
        self._aprs = BotAprsHandler("", self)
        self._config_file = config_file
        self._config_mtime = None
        self._cfg = configparser.ConfigParser()
        self._cfg.optionxform = str  # config is case-sensitive
        self._check_updated_config()
        self._last_blns = time.monotonic()
        self._last_cron_blns = 0
        self._last_status = time.monotonic()
        self._last_reconnect_attempt = 0
        self._rem = remotecmd.RemoteCommandHandler()


    def _load_config(self):
        try:
            self._cfg.clear()
            self._cfg.read(self._config_file)
            self.addr = self._cfg["tnc"]["addr"]
            self.port = int(self._cfg["tnc"]["port"])
            self._aprs.callsign = self._cfg["aprs"]["callsign"]
            self._aprs.path = self._cfg["aprs"]["path"]
        except Exception as exc:
            logger.error(exc)

    def _check_updated_config(self):
        try:
            mtime = os.stat(self._config_file).st_mtime
            if self._config_mtime != mtime:
                self._load_config()
                self._config_mtime = mtime
                logger.info("Configuration reloaded")
        except Exception as exc:
            logger.error(exc)

    def on_connect(self):
        logger.info("Connected")

    def on_disconnect(self):
        logger.warning("Disconnected! Will try again soon...")
        recon = 'sudo systemctl restart ioreth'
        os.system(recon)


    def on_recv_frame(self, frame):
        self._aprs.handle_frame(frame)
    def _update_bulletins(self):
        if not self._cfg.has_section("bulletins"):
            return

        max_age = self._cfg.getint("bulletins", "send_freq", fallback=600)

        # There are two different time bases here: simple bulletins are based
        # on intervals, so we can use monotonic timers to prevent any crazy
        # behavior if the clock is adjusted and start them at arbitrary moments
        # so we don't need to worry about transmissions being concentrated at
        # some magic moments. Rule-based blns are based on wall-clock time, so
        # we must ensure they are checked exactly once a minute, behaves
        # correctly when the clock is adjusted, and distribute the transmission
        # times to prevent packet storms at the start of minute.

        now_mono = time.monotonic()
        now_time = time.time()

        # Optimization: return ASAP if nothing to do.
        if (now_mono <= (self._last_blns + max_age)) and (
            now_time <= (self._last_cron_blns + 60)
        ):
            return

        bln_map = dict()

        # Find all standard (non rule-based) bulletins.
        keys = self._cfg.options("bulletins")
        keys.sort()
        std_blns = [
            k for k in keys if k.startswith("BLN") and len(k) > 3 and "_" not in k
        ]

        # Do not run if time was not set yet (e.g. Raspberry Pis getting their
        # time from NTP but before conecting to the network)
        time_was_set = time.gmtime().tm_year > 2000

        # Map all matching rule-based bulletins.
        if time_was_set and now_time > (self._last_cron_blns + 60):
            # Randomize the delay until next check to prevent packet storms
            # in the first seconds following a minute. It will, of course,
            # still run within the minute.
            timestr = time.strftime("%Y%m%d")
            timestrtxt = time.strftime("%m%d")
            filename1 = "/home/pi/ioreth/ioreth/ioreth/netlog-"+timestr

            self._last_cron_blns = 60 * int(now_time / 60.0) + random.randint(0, 30)

            cur_time = time.localtime()
            utc_offset = cur_time.tm_gmtoff / 3600  # UTC offset in hours
            ref_time = cur_time[:5]  # (Y, M, D, hour, min)

            for k in keys:
                # if key is "BLNx_rule_x", etc.
                lst = k.split("_", 3)
                if (
                    len(lst) == 3
                    and lst[0].startswith("BLN")
                    and lst[1] == "rule"
                    and (lst[0] not in std_blns)
                ):
                    expr = CronExpression(self._cfg.get("bulletins", k))
                    if expr.check_trigger(ref_time, utc_offset):
                        bln_map[lst[0]] = expr.comment

        # If we need to send standard bulletins now, copy them to the map.
        if now_mono > (self._last_blns + max_age):
            self._last_blns = now_mono
            for k in std_blns:
                bln_map[k] = self._cfg.get("bulletins", k)

        if len(bln_map) > 0:
            to_send = [(k, v) for k, v in bln_map.items()]
            to_send.sort()
            for (bln, text) in to_send:
                logger.info("Posting bulletin: %s=%s", bln, text)
                self._aprs.send_aprs_msg(bln, text)

# These lines are for checking if there are SMS messages received. Maybe find a better place for it
# but the bulletins portion of the code might be the best place, as there may be no need to poll
# for new SMS every so often.

        smsinbox = "/var/spool/gammu/inbox/"
        smsfolder = os.listdir(smsinbox)
        smsinbox = "/var/spool/gammu/inbox/"
        smsfolder = os.listdir(smsinbox)
        smsalias = 0
        if len(smsfolder)>0:
            for filename in os.listdir(smsinbox):
                    smsnumber = filename[24:34]
                    smssender = "0"+smsnumber
                    logger.info("Found message in SMS inbox. Now processing.")
                    smsalias = "none"
                    smstxt = open(smsinbox + filename, 'r')
                    smsread = smstxt.read()
                    smsreceived = smsread.replace('\n',' ')
                    smstxt.close()
                    prefix = filename[22:25]
                    smsstart = smsreceived.split(' ',1)[0]
                    smsstartupper = smsstart.upper()
# Ignore if from self
                    if smssender == "09760685303":
                       logger.info("Found message from self. Removing.")
                       movespam = ("sudo rm "+ smsinbox + filename)
                       os.system(movespam)
                       return

                    if not prefix == "639":
                               logger.info("Possibly a carrier message or spam from %s. No longer processing", smssender )
                               movespam = ("sudo mv "+ smsinbox + filename + " /var/spool/gammu/spam")
                               os.system(movespam)
                    else:
# Let cell user create an alias
  
                      if smsstartupper == "ALIAS":
                          cellaliasfile = "/home/pi/ioreth/ioreth/ioreth/smsalias/CELLULAR"
                          isbodyalias = len(smsreceived.split())
                          if isbodyalias > 1 :
                              cellownalias = smsreceived.split(' ', 1)[1]
                              logger.info("Alias body found. Setting self alias")
                          else:
                              cellownalias = ""
                          aliastext = smssender + " " + cellownalias
                          with open(cellaliasfile, 'a') as makealias:
                              writealias = "{} {}\n".format(smssender, cellownalias)
                              makealias.write(writealias)
                          sendsms = ( "echo 'U have set ur own alias as " + cellownalias + ". Ur # will not appear on msgs. aprsph(.)net for more info.' | gammu-smsd-inject TEXT 0" + smsnumber )
                          os.system(sendsms)
                          logger.info("Self-determined alias set for for %s as %s.", smsnumber, cellownalias )


                      elif smsreceived[0:1] == "@":
                          callsig = smsreceived.split(' ', 1)[0]
                          callsign = callsig.upper()
                          callnossid = callsign.split('-', 1)[0]
                          isbody = len(smsreceived.split())
                          if isbody > 1 :
                              smsbody = smsreceived.split(' ', 1)[1]
                              logger.info("Message body found. Sending message")
                          else:
                              smsbody = "EMPTY MSG BODY"
                              logger.info("Message body not found. Sending empty")
# Let's check if the sender has an alias, and if so we use that instead of the number for privacy.
                          aliaspath = "/home/pi/ioreth/ioreth/ioreth/smsalias/"
                          aliascheck = aliaspath + callnossid[1:]
                          cellaliascheck = aliaspath + "CELLULAR"
# Let's check if the sender has a self-assigned alias
                          lines = []
                          cellsmsalias = 0
                          with open(cellaliascheck, 'r') as file:
                              lines = file.readlines()
                          count = 0
                          for line in lines:
                              count += 1
                              names = line.replace('\n','')
                              alias = names[12:]
                              logger.info("Trying to match '%s' with '%s'.", smsnumber, names )
                              if smsnumber == names[1:11]:
                                    smssender = alias
                                    cellsmsalias = 1
                                    logger.info("Self-determined alias found for %s as %s.", smsnumber, alias )
# But, the CALLSIGN's own alias file takes precedence over self-determined aliases, so check this also.
                          if not os.path.isfile(aliascheck):
#                               smssender = "0" + smsnumber
                               logger.info("No alias file found at %s%s, using SMS-defined alias or number.", aliaspath, callnossid[1:] )
                               smsalias = 0
                          else:
                               logger.info("Alias file found, trying to match '%s' to an alias.",smsnumber )
                               lines = []
                               with open(aliascheck, 'r') as file:
                                  lines = file.readlines()
                               count = 0
                               for line in lines:
                                   count += 1
                                   names = line.replace('\n','')
                                   alias = names[12:]
                                   logger.info("Trying to match '%s' with '%s'.", smsnumber, names )
                                   if smsnumber == names[1:11]:
                                         smssender = alias
                                         smsalias = 1
                                         logger.info("Alias found for %s as %s.", smsnumber, alias )
# Now send  the message. Split it if too long.
                          if len(smsbody) > 50:
                               smsbody1 = smsbody[0:47]
                               smsbody2 = smsbody[47:110]
                               smsbody3 = smsbody[110:173]
                               smsbody4 = smsbody[173:]
                               if len(smsbody) >= 48 and len(smsbody) <= 110:
                                  self._aprs.send_aprs_msg(callsign[1:], "SMS " + smssender + " 1/2:" + smsbody1)
                                  self._aprs.send_aprs_msg(callsign[1:], "2/2:" + smsbody2)
                                  self._aprs.send_aprs_msg(callsign[1:], "SMS " + smssender + " Message to send/reply to PH SMS.")
                                  logger.info("SMS too long to fit 1 APRS message. Splitting into 2.")
                               if len(smsbody) >= 111 and len(smsbody) <= 173:
                                  self._aprs.send_aprs_msg(callsign[1:], "SMS " + smssender + " 1/3:" + smsbody1)
                                  self._aprs.send_aprs_msg(callsign[1:], "2/3:" + smsbody2)
                                  self._aprs.send_aprs_msg(callsign[1:], "3/3:" + smsbody3)
                                  self._aprs.send_aprs_msg(callsign[1:], "SMS " + smssender + " Message to send/reply to PH SMS.")
                                  logger.info("SMS too long to fit 1 APRS message. Splitting into 3.")
                               if len(smsbody) >= 173:
                                  self._aprs.send_aprs_msg(callsign[1:], "SMS " + smssender + " 1/4:" + smsbody1)
                                  self._aprs.send_aprs_msg(callsign[1:], "2/4:" + smsbody2)
                                  self._aprs.send_aprs_msg(callsign[1:], "3/4:" + smsbody3)
                                  self._aprs.send_aprs_msg(callsign[1:], "4/4:" + smsbody4)
                                  self._aprs.send_aprs_msg(callsign[1:], "SMS " + smssender + " Message to send/reply to PH SMS.")
                                  logger.info("SMS too long to fit 1 APRS message. Splitting into 4.")
                          else:
                               self._aprs.send_aprs_msg(callsign[1:], "SMS " + smssender + ":" + smsbody)
                               self._aprs.send_aprs_msg(callsign[1:], "SMS " + smssender + " Message to send/reply to PH SMS.")
                               logger.info("SMS is in correct format. Sending to %s.", callsign)
                          if smsalias == 1 or cellsmsalias == 1:
                               sendsms = ( "echo 'APRS msg to " + callsign[1:] + " has been sent. APRS msgs not private, but ur # has an alias & will not appear. aprsph . net for more info.' | gammu-smsd-inject TEXT 0" + smsnumber )
                          else:
                               sendsms = ( "echo 'APRS msg to " + callsign[1:] + " sent. Ur # & msg may appear on online services. Send ALIAS yourname to set an alias. Go aprsph.net for more info.' | gammu-smsd-inject TEXT 0" + smsnumber )
                          logger.info("Sending %s a confirmation message that APRS message has been sent.", smssender)
                          os.system(sendsms)
                      else:
#                          if smsalias == 1:
                          sendsms = ( "echo 'To text APRS user: \n\n@CALSGN-SSID Message\n\nMust hv @ b4 CS (SSID optional if none). To set ur alias & mask ur cell#:\n\nALIAS myname\n\naprsph . net for info.' | gammu-smsd-inject TEXT 0" + smsnumber )
#                          else:
#                                sendsms = ( "echo 'Incorrect format.Use: \n\n@CALSGN-SSID Message\n\nto text APRS user. Must have @ before CS. 1/2-digit SSID optional if none.' | gammu-smsd-inject TEXT 0" + smsnumber )


                          os.system(sendsms)
                    movecmd = ("sudo mv "+ smsinbox + filename + " /var/spool/gammu/processed")
                    os.system(movecmd)
                    logger.info("Cleaning up SMS inbox.")

# These lines are for maintaining the net logs
        if os.path.isfile('/home/pi/ioreth/ioreth/ioreth/netlog'):
           file = open('/home/pi/ioreth/ioreth/ioreth/netlog', 'r')
           data20 = file.read()
           file.close()
           fout = open(filename1, 'a')
           fout.write(data20)
           fout.write(",")
           fout = open(filename3, 'a')
           fout.write(data20)
           fout.write("\n")
           logger.info("Copying latest checkin into day's net logs")
           os.remove('/home/pi/ioreth/ioreth/ioreth/netlog')
           logger.info("Deleting net log scratch file")
           timestrtxt = time.strftime("%m%d")
           file = open(filename1, 'r')
           data5 = file.read()  
           file.close()
           if len(data5) > 310 :
                       listbody1 = data5[0:58]
                       listbody2 = data5[58:121]
                       listbody3 = data5[121:184]
                       listbody4 = data5[184:247]
                       listbody5 = data5[247:310]
                       listbody6 = data5[310:]
                       self._aprs.send_aprs_msg("BLN3NET", timestrtxt + " 1/6:" + listbody1)
                       self._aprs.send_aprs_msg("BLN4NET", "2/6:" + listbody2 )
                       self._aprs.send_aprs_msg("BLN5NET", "3/6:" + listbody3 )
                       self._aprs.send_aprs_msg("BLN6NET", "4/6:" + listbody4 )
                       self._aprs.send_aprs_msg("BLN7NET", "5/6:" + listbody5 )
                       self._aprs.send_aprs_msg("BLN8NET", "6/6:" + listbody6 )
           if len(data5) > 247 and len(data5) <= 310 :
                       listbody1 = data5[0:58]
                       listbody2 = data5[58:121]
                       listbody3 = data5[121:184]
                       listbody4 = data5[184:247]
                       listbody5 = data5[247:310]
                       self._aprs.send_aprs_msg("BLN4NET", timestrtxt + " 1/5:" + listbody1)
                       self._aprs.send_aprs_msg("BLN5NET", "2/5:" + listbody2 )
                       self._aprs.send_aprs_msg("BLN6NET", "3/5:" + listbody3 )
                       self._aprs.send_aprs_msg("BLN7NET", "4/5:" + listbody4 )
                       self._aprs.send_aprs_msg("BLN8NET", "5/5:" + listbody5 )
           if len(data5) > 184 and len(data5) <= 247 :
                       listbody1 = data5[0:58]
                       listbody2 = data5[58:121]
                       listbody3 = data5[121:184]
                       listbody4 = data5[184:]
                       self._aprs.send_aprs_msg("BLN5NET", timestrtxt + " 1/4:" + listbody1)
                       self._aprs.send_aprs_msg("BLN6NET", "2/4:" + listbody2 )
                       self._aprs.send_aprs_msg("BLN7NET", "3/4:" + listbody3 )
                       self._aprs.send_aprs_msg("BLN8NET", "4/4:" + listbody4 )
           if len(data5) > 121 and len(data5) <= 184:
                       listbody1 = data5[0:58]
                       listbody2 = data5[58:121]
                       listbody3 = data5[121:]
                       self._aprs.send_aprs_msg("BLN6NET", timestrtxt + " 1/3:" + listbody1)
                       self._aprs.send_aprs_msg("BLN7NET", "2/3:" + listbody2 )
                       self._aprs.send_aprs_msg("BLN8NET", "3/3:" + listbody3 )
           if len(data5) > 58 and len(data5) <= 121:
                       listbody1 = data5[0:58]
                       listbody2 = data5[58:]
                       self._aprs.send_aprs_msg("BLN6NET", timestrtxt + " 1/2:" + listbody1)
                       self._aprs.send_aprs_msg("BLN7NET", "2/2:" + listbody2 )
           if len(data5) <= 58:
                       self._aprs.send_aprs_msg("BLN6NET", timestrtxt + ":" + data5)
           self._aprs.send_aprs_msg("BLN9NET", "Full logs and more info at https://aprsph.net")
           logger.info("Sending new log text to BLN7NET to BLN8NET after copying over to daily log")

        if os.path.isfile('/home/pi/ioreth/ioreth/ioreth/nettext'):
#           file = open('/home/pi/ioreth/ioreth/ioreth/nettext', 'r')
#           data4 = file.read()  
#           file.close()
# Deprecated the lines below. We are now writing the login text directly, since the previous method resulted in
# Simultaneous checkins not being logged properly. The purpose now is to use the nettext file as a flag whether to
# upload the net logs to the web.
#           fout = open('/home/pi/ioreth/ioreth/ioreth/netlog-msg', 'a')
#           fout.write(data4)
#           fout.write("\n")
#           fout.close()
#           logger.info("Copying latest checkin message into cumulative net log")
           os.remove('/home/pi/ioreth/ioreth/ioreth/nettext')
           logger.info("Deleting net text scratch file")
           cmd = 'scp /home/pi/ioreth/ioreth/ioreth/netlog-msg root@radio1.dx1arm.net:/var/www/aprsph.net/public_html/index.html'
#           cmd = 'scp /home/pi/ioreth/ioreth/ioreth/netlog-msg root@radio1.dx1arm.net:/var/www/html/aprsnet'
           try:
              os.system(cmd)
              logger.info("Uploading logfile to the web")
           except:
              logger.info("ERRIR in uploading logfile to the web")

        if os.path.isfile('/home/pi/ioreth/ioreth/ioreth/aprsthursdaytext'):
           os.remove('/home/pi/ioreth/ioreth/ioreth/aprsthursdaytext')
           logger.info("Deleting aprsthursday net text scratch file")
           cmd = 'scp /home/pi/ioreth/ioreth/ioreth/aprsthursday/index.html root@radio1.dx1arm.net:/var/www/aprsph.net/public_html/aprsthursday/index.html'
#           cmd = 'scp /home/pi/ioreth/ioreth/ioreth/netlog-msg root@radio1.dx1arm.net:/var/www/html/aprsnet'
           try:
              os.system(cmd)
              logger.info("Uploading aprsthursday logfile to the web")
           except:
              logger.info("ERRIR in uploading logfile to the web")



    def send_aprs_msg(self, to_call, text):
        self._client.enqueue_frame(self.make_aprs_msg(to_call, text))

    def _update_status(self):
        if not self._cfg.has_section("status"):
            return

        max_age = self._cfg.getint("status", "send_freq", fallback=600)
        now_mono = time.monotonic()
        if now_mono < (self._last_status + max_age):
            return

        self._last_status = now_mono
        self._rem.post_cmd(SystemStatusCommand(self._cfg["status"]))



    def _check_reconnection(self):
        if self.is_connected():
            return
        try:
            # Server is in localhost, no need for a fancy exponential backoff.
            if time.monotonic() > self._last_reconnect_attempt + 5:
                logger.info("Trying to reconnect")
                self._last_reconnect_attempt = time.monotonic()
                self.connect()
        except ConnectionRefusedError as e:
            logger.warning(e)

    def on_loop_hook(self):
        AprsClient.on_loop_hook(self)
        self._check_updated_config()
        self._check_reconnection()
        self._update_bulletins()
        self._update_status()

        # Poll results from external commands, if any.
        while True:
            rcmd = self._rem.poll_ret()
            if not rcmd:
                break
            self.on_remote_command_result(rcmd)

    def on_remote_command_result(self, cmd):
        logger.debug("ret = %s", cmd)

        if isinstance(cmd, SystemStatusCommand):
            self._aprs.send_aprs_status(cmd.status_str)

