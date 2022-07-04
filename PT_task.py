from __future__ import print_function
import argparse
import json
import pdb
import os
import random
import sys
import time
from datetime import datetime
import tty
import termios

from NAO import Camera, Speech, Movements, ReactToTouch, isData


def clearline(times=1):
    for t in range(times):
        print("\033[A\033[A")
        print(" "*128)
        print("\033[A\033[A")


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def printcolored(text, color=bcolors.HEADER, end='\n'):
    print(color+text+bcolors.ENDC, end=end)


class Task():
    '''
    This class simulates the robot
    '''

    def __init__(self, args):
        self.mode = args.group

        try:
            with open("participants_info.json") as file:
                names = json.load(file)
            self.participant_name = str(names[str(args.id)][0]) # "<id number>": [ "<name>", ... ]
        except:
            self.participant_name = ""

        self._readJSON()

        self.code_so_far = ""

        self.instruction_id = 0  # id of the object

        self.results = { # dictionaire with all the statical information 
            "Group": self.mode,
            "ID of the Participant": args.id
            }  

        self.path = ("",False)
        self.interaction_time = 0

        # attention to the order
        self.movements = Movements(args.ip, args.port)    # needs to go first to activate the robot and put it in position
        self.camera = Camera(args.ip, args.port)          # goes in second to start tracking the human
        self.speech = Speech(args.ip, args.port)          # does not have hurry to initiate

        global ReactToTouch
        ReactToTouch = ReactToTouch(args.ip, args.port, "ReactToTouch")

    def introduction(self):
        
        # waits for the participant to be ready
        while(ReactToTouch.wait_for_touch):
            self.speech.leds.my_fade("AllLeds", 0.2)

            if self.camera.get_landmark(0.3) != -1:
                self.speech.say("Landmark detected")

            if isData():
                woz = sys.stdin.read(1)
                if woz == "t":
                    printcolored("Wizard of OZ: Touch", bcolors.WARNING)
                    break
                else: printcolored("Wizard of OZ: '"+woz+"' not available", bcolors.FAIL)

        self.interaction_time = datetime.now()
        
        self.movements.track_face()
        # Waits for the robot to start tracking the participant
        while self.movements.tracker_service.isTargetLost():
            print("\rSearching for the user",end="")
        print("\t User Found!!")

        self.path = self.speech.introduction(self.participant_name)   # introduces itself
       
        self.speech.say("Get ready, because with no further ado, we are going to start the game.")
        time.sleep(2)

    def _readJSON(self):
        with open("instructions.json") as file:
            instructions = json.load(file)

        self.instructions = {}
        # unicode to ascii
        for k, v in instructions.items():
            # get new key
            new_key = str(k).replace("u'", "'")
            self.instructions[new_key] = {}
            # replace value
            for k2, v2 in v.items():
                new_subkey = str(k2).replace("u'", "'")
                self.instructions[new_key][new_subkey] = []
                for elem in v2:
                    self.instructions[new_key][new_subkey].append(
                        str(elem).replace("u'", "'"))

        # sort elements by order and then extract the object sequence
        dictionary_items = self.instructions[self.mode].items()
        sorted_tuple = sorted(dictionary_items, key=lambda x: int(x[0]))
        self.code = [obj[1][0] for obj in sorted_tuple]

    def _ask_object(self, ambiguity=False):

        instruction_id = self.instruction_id
        if not ambiguity:
            instruction = "Go with the " + \
                self.instructions[self.mode][str(instruction_id)][1] + "."
        else:
            instruction = "Go with the " + \
                self.instructions[self.mode][str(instruction_id)][1] + "."
            instruction = instruction.replace(
                self.instructions[self.mode][str(instruction_id)][2],
                self.instructions[self.mode][str(instruction_id)][3]
            )
        printcolored("Instruction: "+str(self.instruction_id), bcolors.OKBLUE)
        self.speech.say(instruction)

    def _get_object_id(self):

        # during x seconds, will have the Speech recognition on, and uses the camera time as the sample interval
        available_reaction_time, frequency = 15, 2
        wizard_of_oz = False
        self.speech.start_listen()
        user_answer = ""
        t_pause = 0

        for _ in range(int(available_reaction_time*frequency)):
            guess_id = self.camera.get_landmark(1.0/frequency)
            if guess_id != -1: break # breaks if scans a landmark
            if self.speech.step_listen("ambiguity", "repetition"): break # attention, because when it is pause, it return false and restarts from here
            
            # Wizard of Oz
            if isData():
                woz = sys.stdin.read(1)
                wizard_of_oz = True
                if woz == 'a': # ambiguity
                    printcolored("Wizard of OZ: Ambiguity", bcolors.WARNING)
                    user_answer = "ambiguity"
                    break    
                elif woz == 'p': # enters in pause
                    printcolored("Wizard of OZ: Starting Pause", bcolors.WARNING)
                    t_pause_start = datetime.now()
                    self.speech.pause() 
                    wizard_of_oz = False    # there is no interference
                    t_pause += (datetime.now()-t_pause_start).total_seconds()
                elif woz == 'r': # repeat
                    printcolored("Wizard of OZ: Repetition", bcolors.WARNING)
                    user_answer = "repetition"
                    break
                elif woz == 'k': # Not understanding
                    printcolored("Wizard of OZ:  Does not understand", bcolors.WARNING)
                    self.speech.say("I am sorry but I don't know how to answer your question at the moment.")
                    user_answer = "repetition"
                    break   
                elif woz == 'l': # Talk later
                    printcolored("Wizard of OZ: Talk that later", bcolors.WARNING)
                    self.speech.say("That is an interesting intervention. Maybe we can talk about it later, after completing the task.")
                    user_answer = "repetition"
                    break 
                elif woz == 'c': # continue, corrrect object
                    guess_id = self.code[self.instruction_id-1]
                    printcolored("Wizard of OZ: Correct Object", bcolors.WARNING)
                    self.speech.stop_listen()
                    return str(guess_id), t_pause
                # maybe if the landmarks are not working the answer can be inputted with woz
                try:
                    _ = int(woz)
                    printcolored("Wizard of OZ: Landmark", bcolors.WARNING)
                    self.speech.stop_listen()
                    return woz, t_pause
                except:
                    if woz != 'p': printcolored("Wizard of OZ: '"+woz+"' not available", bcolors.FAIL)

            # Pause the program when robot cannot track the user
            if self.movements.tracker_service.isTargetLost():
                self.speech.stop_listen()   # stops the speech recognizer
                print("User is not looking...\t",end="")
                sys.stdout.flush()
                while self.movements.tracker_service.isTargetLost(): time.sleep(0.5) # waits here until have the attention back
                print("... and it is looking again!",)
                self.speech.start_listen()  # restart the speech recognizer

        # has to stop the speech recognizer
        if wizard_of_oz: self.speech.stop_listen()
        else: user_answer = self.speech.stop_listen()

        if guess_id == '?' or user_answer == "ambiguity":   # detects ambiguities
            return '?', t_pause
        elif guess_id == -1 or user_answer == "repetition":    # no answer or human asked for repetition
            return "+", t_pause

        # after humans answer, in base of keyboard basically 
        try:
            guess_id = int(guess_id)
            if (guess_id < 0 or guess_id > 9):
                raise ValueError
        except:
            printcolored(guess_id, bcolors.FAIL, '')
            print(bcolors.WARNING+"Enter a number between [0-9]."+bcolors.ENDC,
                  "The answer:", bcolors.UNDERLINE, guess_id, bcolors.ENDC, "is not valid.")
            guess_id = self._get_object_id()

        return str(guess_id), t_pause

    def _check_object(self, guess_id=""):
        # checks if it is the correct value
        is_correct = guess_id == self.code[self.instruction_id-1]

        printcolored("Key:\t", bcolors.HEADER, '')
        printcolored(self.code_so_far, bcolors.OKGREEN, '')
        if is_correct:
            printcolored(guess_id, bcolors.OKGREEN)
            self.code_so_far += str(guess_id)
            self.speech.correct_answer(0.5)
        else:
            printcolored(guess_id, bcolors.FAIL)
            self.speech.incorrect_answer(0.5)

        return is_correct

    def _open_locker(self):
        self.speech.say( "Ok, we deciphered the code. \\pau=500\\ Please show me any two objects to access the system, at the same time.")

        counter, freq_sample, available_time = 1, 2, 10
        self.speech.start_listen()

        while(self.camera.get_landmark(1.0/freq_sample, 2) < 1):
            if counter % (available_time*freq_sample) == 0:
                self.speech.say("Please show me any 2 objects, at the same time,")
            self.speech.step_listen(False)
            counter += 1

            if isData():
                woz = sys.stdin.read(1)
                if woz == "c":
                    printcolored("Wizard of OZ: Continue", bcolors.WARNING)
                    break
                elif woz == 'k': # Not understanding
                    printcolored("Wizard of OZ:  Does not understand", bcolors.WARNING)
                    self.speech.say("I am sorry but I don't know how to answer your question at the moment.")
                elif woz == "r":
                    printcolored("Wizard of OZ: Repeat", bcolors.WARNING)
                    self.speech.say("Please show me any 2 objects at the same time!")
                elif woz == "b":
                    printcolored("Wizard of OZ: Open box", bcolors.WARNING)
                    self.speech.say("You can open the box!")
                elif woz == "p":
                    self.speech.pause()
                else:
                    printcolored("Wizard of OZ: '"+woz+"' not available", bcolors.FAIL)
            
        self.speech.stop_listen()

        self.speech.say("Nice job, the key to open the locker is 195!")
     
    def perspective_taking(self):
        
        perspective_Taking_task_time = datetime.now()

        while self.instruction_id < len(self.code):

            # increase the object
            self.instruction_id += 1

            # stays in the object until the user got it right
            correct_pick = False

            # flag to validate when an ambiguity happened
            user_claims_ambiguity = False

            # flag to check if the sentence is ambiguous because of multiple answers or due to unknown reference frame
            has_ambiguity = len(self.instructions[self.mode][str(self.instruction_id)]) > 2
            # lets define the define mental model according to the robot intention
            if has_ambiguity:
                mental_model = "allocentric" if self.mode == "robot" else "egocentric" if self.mode == "human" else None
            
            # auxiliary variable to measure the partial time in each question, the ambiguities, and so on
            n_tries, t_partial, n_mistakes, n_help = 0, 0, -1, 0
            # if the program is right: n_tries == n_mistakes + n_help + 1 (correct guess)

            while(not correct_pick):
                n_tries += 1
                n_mistakes += 1 

                # start by asking for the object
                self._ask_object(user_claims_ambiguity)

                # process the input
                t_partial_start = datetime.now()
                guess_id, t_partial_stop = self._get_object_id()
                t_partial += (datetime.now()-t_partial_start).total_seconds()-t_partial_stop

                # in case of ambiguity
                if guess_id == '?':
                    if has_ambiguity:
                        user_claims_ambiguity = True
                    else:
                        self.speech.say("Sorry, that was as clear as I can be in this instruction. Let's do it again.")
                        time.sleep(0.25)

                    n_help += 1
                    n_mistakes -= 1 # when user asks for help, there is no mistake
                    continue
                
                elif guess_id == '+':
                    n_mistakes -= 1 # when user asks for repetition, there is no mistake
                    n_tries -= 1
                    continue

                # check if it is the right number
                correct_pick = self._check_object(guess_id)

                if has_ambiguity and self.mode != "control" and guess_id == self.instructions[self.mode][str(self.instruction_id)][4]:
                    mental_model = "egocentric" if self.mode == "robot" else "allocentric"
            
                    
            self.results["Time Q"+str(self.instruction_id)] = round(t_partial,2)
            self.results["Help Q"+str(self.instruction_id)] = n_help
            self.results["Mistakes Q"+str(self.instruction_id)] = n_mistakes
            self.results["Tries Q"+str(self.instruction_id)] = n_tries
            if has_ambiguity: self.results["Mental Model Q"+str(self.instruction_id)] = mental_model

        # stops the perspective taking interaction time
        self.results["Perspective Taking Task Time"] = round((datetime.now()-perspective_Taking_task_time).total_seconds(),2)

        # Perspective taking task done, now it is time to open the locker
        self._open_locker()

        # register the user
        self.camera.take_photo(self.path)

        # stops tracking the participant
        self.movements.tracker_service.stopTracker()

    def prosocial_behaviour(self):
        global ReactToTouch

        # informs the robot, that it accpets head touch again - Start the interaction
        ReactToTouch.set_touch(True)

        # waits for the participant to be ready
        while(ReactToTouch.wait_for_touch):
            self.speech.leds.my_fade("AllLeds", 0.5)
            if isData():
                woz = sys.stdin.read(1)
                if woz == "t":
                    printcolored("Wizard of OZ: Touch", bcolors.WARNING)
                    break
                elif woz == "b":
                    printcolored("Wizard of OZ: Open box", bcolors.WARNING)
                    self.speech.say("You can open the box!")
                elif woz == "c":
                    printcolored("Wizard of OZ: Code", bcolors.WARNING)
                    self.speech.say("The code to open the box is 195!")
                else: printcolored("Wizard of OZ: '"+woz+"' not available", bcolors.FAIL)

        self.speech.say("""
Thanks for showing interest. I highlight again that this part is voluntary, and you can leave at any time. \\pau=500\\
I can detect emotions in human faces, although I cannot express emotions in my speech accordingly. \\pau=200\\ This task is about understanding how your voice changes when you express yourself with different emotions. \\pau=200\\ In this task, a sentence will be prompted, and I would like to hear how you read it with the emotion also prompted on the screen. \\pau=200\\ Check the sentence if you read it!\\pau=500\\
At this point, you can switch on the screen on your right, by touching the button under the yellow arrow.""")

        # accepts the stop of the iteraction
        ReactToTouch.set_touch(True)

        while(ReactToTouch.wait_for_touch):
            self.speech.leds.my_fade("AllLeds", 0.5)

            if isData():
                woz = sys.stdin.read(1)
                if woz == "t":
                    printcolored("Wizard of OZ: Touch", bcolors.WARNING)
                    break
                elif woz == "s":
                    printcolored("Wizard of OZ: switch screen on", bcolors.WARNING)
                    self.speech.say("At this point, you can switch on the screen on your right, by touching the button under the yellow arrow.")
                else: printcolored("Wizard of OZ: '"+woz+"' not available", bcolors.FAIL)

        # starting the task
        self.speech.say("Lets start the task, good luck!")

        # starts measuring the time
        reading_time = datetime.now()

        # register the time when the participant started the task
        self.results["Prosocial Behaviour Starting Time"] = reading_time.strftime("%Y/%m/%d %H:%M:%S")

        task.save_results(False)

        # accepts the stop of the iteraction
        ReactToTouch.set_touch(True)

        while(ReactToTouch.wait_for_touch):
            self.speech.leds.my_fade("AllLeds", 0.5)

            if isData():
                woz = sys.stdin.read(1)
                if woz == "t":
                    printcolored("Wizard of OZ: Touch", bcolors.WARNING)
                    break
                elif woz == "s":
                    printcolored("Wizard of OZ: switch screen on", bcolors.WARNING)
                    self.speech.say("At this point, you can switch on the screen by touching the button under the mark.")
                else: printcolored("Wizard of OZ: '"+woz+"' not available", bcolors.FAIL)


        # looks at the participant again
        self.movements.track_face()
        self.speech.say("Thanks for helping me. I hope to interact with you again.")
    
    def save_results(self, force_quit=False):

        # save the total time
        try: self.results["Total Interaction Time"] = round((datetime.now()-self.interaction_time).total_seconds(),2)
        except: pass # interaction have not started

        # save stats in the file
        self.results["Force Quit"] = force_quit
        if self.path[1]:
            with open(self.path[0]+'/stats.json', 'w') as fp:
                json.dump(self.results, fp, sort_keys=True, indent=4)

    def stop(self):

        print("Stopping...")
        self.speech.say("bye, nari.")

        # safely stoping the robot      
        self.speech.stop()
        self.camera.stop()
        self.movements.stop()

        global ReactToTouch
        ReactToTouch.stop()
        
if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description='Choose the type of perspective taking.')
    parser.add_argument(
        '--group',
        choices=['control', 'robot', 'human'],
        help="\nSelect the option in order to test the following perspective taking: 'control' - the robot refers the objects based on others, 'robot' - robot is egocentric, 'human' - robot is addressee centered ")

    parser.add_argument("--ip", type=str, default="192.168.1.218", help="Robot IP address. On robot or Local Naoqi: use '127.0.0.1'.")

    parser.add_argument("--port", type=int, default=9559, help="Naoqi port number")
                    
    parser.add_argument("--id", type=int, default=0, help="ID of the participant. = is for 'test")

    # args = parser.parse_args(['--group control --id 1'])
    args = parser.parse_args()
    old_settings = termios.tcgetattr(sys.stdin)

    try:
        tty.setcbreak(sys.stdin.fileno())

        os.system("clear")
        printcolored("Starting the interaction ...\n")

        task = Task(args)

        task.introduction()

        # Perspective Taken task
        task.perspective_taking()

        # opening the locker, find the prize + answer the questionnaires
        time.sleep(10)  # waits for a while and then is available to receive touch

        # starts the prosocial behaviour task
        task.prosocial_behaviour()

    except RuntimeError:
        print ("Can't connect to Naoqi at ip \"" + args.ip + "\" on port " + str(args.port) +".\n"
               "Please check your script arguments. Run with -h option for help.")
        task.save_results(True)
               
    except KeyboardInterrupt:
        print("\033[91mProgram stopped due to: \033[1m Crtl+C \033[0m\033[0m")
        task.save_results(True)

    except Exception, err:
        print("\033[91mProgram stopped due to: \033[1m '" + str(err) + "'\033[0m\033[0m")
        task.save_results(True)
    
    except: # Dunno if this will be triggered but just in case
        task.save_results(True)

    finally: termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    task.stop()

