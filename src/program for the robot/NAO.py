from __future__ import print_function
import time
import pdb
import time
from datetime import datetime
import random
import sys
from PIL import Image
import os
import select

from naoqi import ALProxy
from naoqi import ALBroker
from naoqi import ALModule

# Wizard of OZ
def isData():
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])

class Camera:

    def __init__(self, ip, port):
        # Create a proxy to ALLandMarkDetection
        try:
            self.landmark_proxy = ALProxy("ALLandMarkDetection", ip, port)
            self.video_device_proxy = ALProxy('ALVideoDevice', ip, port)
            self.memory_proxy = ALProxy("ALMemory", ip, port)
        except Exception, e:
            print( "\033[91mError connecting to the speech: switching to keyboard. Error: "+str(e)+"\033[0m")    
            self.virtual_agent = True
        else:
            self.virtual_agent = False

        self.mapping_with_object = (112, 68, 64, 114, 85, 107, 108, 80, 119, 84)

        # to avoid an error in case of previous force exit
        self.stop()

    def take_photo(self, path):
        if path[1] == False: return # only records if the name has more than one character
        folder = path[0]    # path to the folder
        print("Taking the photo ...\t", end="")
        sys.stdout.flush()

        # take a photo of the human
        resolution = 3    # VGA
        colorSpace = 11   # RGB
        fps = 30
        video_client = self.video_device_proxy.subscribe("photo", resolution, colorSpace, fps)    
        naoImage = self.video_device_proxy.getImageRemote(video_client)
        self.video_device_proxy.unsubscribe(video_client)

        # Get the image size and pixel array.
        imageWidth, imageHeight, array = naoImage[0], naoImage[1], naoImage[6]
        image_string = str(bytearray(array))

        # Create a PIL Image from our pixel array.
        im = Image.frombytes("RGB", (imageWidth, imageHeight), image_string)

        # Save the image.
        im.save(folder+"/profile.png", "PNG")

        print("Done")

    def get_landmark(self, period_seconds=10, n_objects=1):
        if self.virtual_agent: return raw_input()
        period_milli = period_seconds*1000.0
        tstart = datetime.now()

        self.landmark_proxy.subscribe("Test_LandMark", period_milli, 0.0)
        
        # Get data from landmark detection (assuming face detection has been activated).

        while((period_milli/1000.0 - (datetime.now()-tstart).total_seconds()) > 0):

            data = self.memory_proxy.getData("LandmarkDetected")

            if data != [] and data is not None:
                landmark = data[1][0][1][0]

                if landmark in self.mapping_with_object and n_objects == 1:
                    return self.mapping_with_object.index(landmark)
                elif landmark in self.mapping_with_object and n_objects > 1:
                    # at least one is on the list and the rest lets confirm
                    for i in data[1]:
                        if i[1][0] not in self.mapping_with_object:
                            return -1
                    else:
                        return len(data[1])
            else:
                # print("\rNo Landmarks detected yet ",end="")
                pass

            time.sleep(0.1)

        return -1

    def stop(self):
        # safely stops all rotines
        try: self.landmark_proxy.unsubscribe("Test_LandMark")
        except: pass  # nothing to report so far
        try: self.video_device_proxy.unsubscribe("photo")
        except: pass  # nothing to report so far


class LEDs:

    def __init__(self, ip, port):
        self.leds = ALProxy("ALLeds", ip, port)
        self.reset('FaceLeds')

    def blink(self, color='magenta', duration=2):
        # available colors: "white", "red", "green", "blue", "yellow", "magenta", "cyan"

        fade_duration = duration/5.0
        self.leds.fadeRGB('FaceLeds', color, fade_duration)
        self.leds.fadeRGB('FaceLeds', "white", fade_duration)
        self.leds.fadeRGB('FaceLeds', color, fade_duration)
        # self.leds.fadeRGB('FaceLeds', "white", fade_duration)
        # self.leds.fadeRGB('FaceLeds', color, fade_duration)

    def reset(self, group): self.leds.reset(group)

    def my_fade(self, group, duration):
        colors = ("white", "red", "green", "blue", "yellow", "magenta", "cyan")
        self.leds.fadeRGB(group, random.choice(colors), duration)

    def stop(self):
        # safely stops all rotines
        try:  self.reset('FaceLeds')
        except: pass  # nothing to report so far


class Speech:

    def __init__(self, ip, port):
        # set up listen capacities
        try:
            self.tts = ALProxy("ALTextToSpeech", ip, port)
            self.asr = ALProxy("ALSpeechRecognition", ip, port)
            self.memProxy = ALProxy("ALMemory", ip, port)
        except Exception, e:
            print( "\033[91mError connecting to the speech: switching to keyboard. Error: "+str(e)+"\033[0m")
            self.virtual_agent = True
        else:
            self.virtual_agent = False

        # set up voice
        self.tts.setLanguage("English")
        self.speed = 80
        self.tts.setVolume(0.5)
        self.tts.setParameter("pitchShift", 1.0)

        # string with words listened
        self.words_listened = []

        # to avoid an error in case of previous force exit
        self.stop()

        self.asr.pause(False)
        self.asr.setLanguage("English")
        self.vocabulary_ambiguity = ("what", "which", "which one", "ambiguity", "multiple",
                                        "ambiguous", "don't understand", "understand", "not", "don't know", "no", "don't", "explain", "didn't", "what color", "which color")
        self.vocabulary_ok = ("ok", "thanks", "nice","Mario")
        self.vocabulary_repetition = ("again", "repeat", "more", "one more time")
        # self.vocabulary_start = ("start","continue", "restart")
        # self.vocabulary_pause = ("pause", "stop", "quite", "wait")

        self.asr.setVocabulary(
            self.vocabulary_ambiguity+self.vocabulary_ok+self.vocabulary_repetition,  # vocabulary
            False  # spotting words
        )

        # set up the leds
        self.leds = LEDs(ip, port)
        
    def introduction(self, name):

        self.say("Hello " + name + ", my name is Nary!")

        # only save if the name has more than one char
        path = "Results/"+name.replace(" ", "")+"_"+datetime.now().strftime("%d-%m-%Y_%H-%M-%S"), len(name)>1
        # test file   
        if name == "test":
            os.system("rm -rf Results/test/")
            path = "Results/test", True
        if path[1]: os.system("mkdir "+path[0])

        return path

    def say(self, text):
        # disable the speech recognition module
        speech_recognition = False
        try:
            self.stop_listen()
            speech_recognition = True
        except: pass 
        # speech to NAO saying
        time.sleep(0.2)  # waits one second before speaking

        # plot in the terminal
        print('\033[96m'+"PEPPER:\t"+'\033[0m', end='')
        print(text)

        # play in NAO's speakers
        self.tts.say("\\rspd="+str(self.speed)+"\\"+text)
        
        if speech_recognition: self.start_listen()

    def listen(self, duration=10):
        # speech recognition for a fixed amount of time
        if self.virtual_agent:
            return []

        # time in seconds
        self.asr.subscribe("Test_ASR")

        frequency = 10
        self.words_listened = []

        print("listening...")
        for i in range(int(duration*frequency)):
            print("listening...")
            time.sleep(1.0/frequency)
            self.words_listened.append(self.memProxy.getData("WordRecognized"))
        self.asr.unsubscribe("Test_ASR")

        return self._intention_detection()

    def start_listen(self):
        # starts the speech recognition
        if self.virtual_agent:
            return
        self.words_listened = []
        self.asr.subscribe("Test_ASR")

    def step_listen(self, *type):
        # samples the speech recognition
        if self.virtual_agent:
            return
        self.words_listened.append(self.memProxy.getData("WordRecognized"))

        # returns true if the type wanted is matched
        return self._intention_detection() in type

    def stop_listen(self):
        # stops the speech recognition
        if self.virtual_agent:
            return
        self.asr.unsubscribe("Test_ASR")

        return self._intention_detection()

    def _intention_detection(self):
        # treat the intention of the speech

         # latest word detected
        try: likely_word = self.words_listened[-1][0]
        except: return ""

         # only validates, if it is a new word and the threshold is more than 40%
        try:
            if self.words_listened[-1] == self.words_listened[-2] or self.words_listened[-1][1] < 0.4: likely_word = ""
        except: pass

        # only accept if the threshold

        likely_intention = ""
        if likely_word in self.vocabulary_ambiguity:
            likely_intention = "ambiguity"
        elif likely_word in self.vocabulary_ok:
            likely_intention = "follow-up"
        elif likely_word in self.vocabulary_repetition:
            likely_intention = "repetition"
        elif likely_word == "":
            likely_intention = "silence"

        # print("Threshold = "+str(self.words_listened[-1][1]))

        print("\033[94mUSER:\t'"+likely_word + "' ("+likely_intention+"); \033[0m")
        sys.stdout.flush()

        return likely_intention

    def pause(self):
        # when something happens and user ask the robot to pause
        try: self.stop_listen()
        except: pass # it was already stopped
        self.say("Pause mode ON.")
        
        while True:
            time.sleep(0.1)
            
            # Wizard of oz
            if isData():
                if sys.stdin.read(1) == "p":
                    print("\033[93mWizard of OZ: Starting Pause\033[91m")
                    self.say("Pause mode OFF.")
                    break
        
        try: self.start_listen()
        except: pass # it was already started

    def correct_answer(self, duration=1):
        # duration in seconds

        # blink first
        self.leds.blink("green", duration)
        # gives feedback with the eyes colored
        self.say(random.choice(
            [
                "Correct object",
                "The object is correct",
                "Thanks for showing"
            ]
        ))
        # goes back to the normal position
        self.leds.reset('FaceLeds')

    def incorrect_answer(self, duration=1):
        # duration in seconds

        # blink first
        self.leds.blink("red", duration)
        # gives feedback with the eyes colored
        self.say(random.choice(
            [
                "Incorrect object",
                "The object is incorrect",
                "Please show me the correct object",
                "That is not the correct object"
            ]
        ))
        # goes back to the normal position
        self.leds.reset('FaceLeds')

    def stop(self):
        # safely stops all rotines
        try: self.asr.unsubscribe("Test_ASR")
        except: pass  # nothing to report so far
        try: self.leds.stop()
        except: pass  # nothing to report so far


class Movements:
    # tracks the movements of the robot

    def __init__(self, ip, port):
        try:
            self.postureProxy = ALProxy("ALRobotPosture", ip, port)
            self.motion_service = ALProxy("ALMotion", ip, port)
            self.tracker_service = ALProxy("ALTracker", ip, port)

        except Exception, e:
            print( "\033[91mError connecting to the proxy: switching to keyboard.\nError: "+str(e)+"\033[0m")
            self.virtual_agent = True
        else:
            self.virtual_agent = False

        # initial position
        self.motion_service.wakeUp()
        self.postureProxy.goToPosture("Sit", 0.5)

    def track_face(self):
    # Add target to track
        targetName = "Face"
        faceWidth = 0.15
        self.tracker_service.registerTarget(targetName, faceWidth)

        # Then, start tracker.
        self.tracker_service.track(targetName)

    def stop(self):
        # safely stops all rotines
        try: self.tracker_service.stopTracker()
        except: pass  # nothing to report so far

        try:
            self.tracker_service.unregisterAllTargets()
            # self.postureProxy.goToPosture("Sit", 0.5)
            self.motion_service.rest()
        except: pass  # nothing to report so far


class ReactToTouch(ALModule):
    """ A simple module able to react
    to touch events.
    """
    def __init__(self, ip, port, name):
      
        self.broker_proxy = ALBroker("myBroker",
            "0.0.0.0",   # listen to anyone
            0,           # find a free port and use it
            ip,          # parent broker IP
            port)        # parent broker port

        try: self._unsubscribe()
        except: pass

        ALModule.__init__(self, name)

        # Subscribe to TouchChanged event:
        self.memory = ALProxy("ALMemory")
        self._subscribe()

        # when True, the robot is wait for an head touch to proceed
        self.set_touch(True)
        self.count_touches = 0

        self.wait_for_touch = True


    def _subscribe(self):
        self.memory.subscribeToEvent("MiddleTactilTouched", "ReactToTouch", "onTouched")


    def _unsubscribe(self):
        self.memory.unsubscribeToEvent("MiddleTactilTouched", "ReactToTouch")

    def onTouched(self):
        """ This will be called each time a touch is detected.  """
        # However, only performs something when the robot is waiting for one
        if self.wait_for_touch:
            # Unsubscribe to the event when talking, to avoid repetitions
            self._unsubscribe()

            self.wait_for_touch = False
            self.count_touches += 1
            print("Touched")
            
            # Subscribs again
            self._subscribe()

    def set_touch(self, value):
        self.wait_for_touch = value
        print("Waiting for the touch in the head ...\t", end="")
        sys.stdout.flush()

    def stop(self):
        self._unsubscribe()
        self.broker_proxy.shutdown()
        

if __name__ == "__main__":
    os.system('python2 game.py --group control --number 0')