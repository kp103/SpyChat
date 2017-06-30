from xyz import spy, Spy, ChatMessage, friends_list
from steganography.steganography import Steganography


SPECIALMSG = ["Hi all"]

STATUS_MSGS = ['hey guys']


def add_status_message():

    updated_status_msg = None

    if spy.current_status_message != None:

        print('Your status: %s \n' % spy.current_status_message)
    else:
        print('Status misses you feed one in!')

    default = raw_input("Choose from the older status (y/n)? ")

    if default[0].upper() == "N":
        new_status_msg = raw_input("New status please")

        if len(new_status_msg)>0:
            if not new_status_msg.decode('utf-8').isspace():
                STATUS_MSGS.append(new_status_msg)
                updated_status_msg = new_status_msg

    elif default[0].upper() == 'Y':

        item_position = 1

        for message in STATUS_MSGS:
            print ('%d. %s' % (item_position, message))
            item_position = item_position + 1

        msg_choice = int(raw_input("\nChoose from the above messages "))


        if len(STATUS_MSGS) >= msg_choice:
            updated_status_msg = STATUS_MSGS[msg_choice - 1]

    else:
        print ('Invalid choice! Be smarter spy. Press either y or n.','red')

    if updated_status_msg:
        print ('Current status: %s' % updated_status_msg)
    else:
        print ('You current don\'t have a status update')

    return updated_status_msg

def add_friend():

    new_friend = Spy('', '', 0, 0.0)

    new_friend.name = raw_input("Your friend's name: ")

    if len(new_friend.name) > 0:
        if new_friend.name.decode('utf-8').isspace():
            print ('Friend name not valid! Be smart spy')
            return -1

    else:
        print ("A nameless friend is not allowed! Try again spy.")
        return -1

    new_friend.salutation = raw_input("Friend's Mr. or Ms.?: ")

    if len(new_friend.salutation) > 0:
        if new_friend.salutation.decode('utf-8').isspace():
            print ('Friend salutation not valid! Be smart spy')
            return -1
    else:
        print ('Friend salutation not valid! Be smart spy')
        return -1
    new_friend.age = raw_input("Age?")

    try:
        new_friend.age = int(new_friend.age)
    except:
        print ("The age has to be numerical Spy! Be smart next time! \n Bye")
        return -1

    new_friend.rating = raw_input("Spy rating?")

    try:
        new_friend.rating = float(new_friend.rating)
    except:
        print ("The rating has to be numerical Spy! Be smart next time! \n Bye!")
        return -1


    if len(new_friend.name) > 0 and new_friend.age > 12 and new_friend.rating >= spy.rating:
        friends_list.append(new_friend)
        print ('New Friend Added!')
    else:
        print ('Sorry! Check the details you\'ve entered again')

    return len(friends_list)

def select_a_friend():
    item_num = 0

    friend_choice_pos=-1
    if len(friends_list) != 0:
        for friend in friends_list:
            print ('%d. %s %s aged %d with rating %.2f is online' % (item_num +1, friend.salutation, friend.name,
                                                       friend.age,
                                                       friend.rating))
            item_num = item_num + 1

        frnd_choice = raw_input("Choose from your friends")

        friend_choice_pos = int(frnd_choice) - 1
        if friend_choice_pos < 0 or friend_choice_pos > len(friends_list)-1:
            print ("The choice doesn't exist Spy! Be smart")
            friend_choice_pos=select_a_friend()
    else:
        addfrnd = raw_input("Add a friend first (y/n)!")
        if addfrnd[0].upper() == 'Y':
            add_friend()
            friend_choice_pos = select_a_friend()
        else:
            print("No friends found!")
            exit(0)
    return friend_choice_pos


def send_message():

    friend_choice = select_a_friend()

    original_img = raw_input("Name of the image in which secret messsage is to be encoded:")

    output_path = "secretspycat.jpg"
    text = raw_input("Your secret message:")
    try:
        Steganography.encode(original_img, output_path, '#'+text)
    except:
        print ("ENCODING UNSUCCESSFUL! MISSION ABORT \n!")
        return

    new_chat = ChatMessage(text,True)

    friends_list[friend_choice].chats.append(new_chat)

    print ("Your secret is safe spy!")

def read_message():

    sender = select_a_friend()

    output_path = raw_input("Secret file name:")

    try:
        secret_msg = Steganography.decode(output_path)
    except:
        print ('Wrong Image! No message.encoded')
        return

    if secret_msg[0] == '#':
        new_chat = ChatMessage(secret_msg[1:], True)
    else:
        new_chat=ChatMessage(secret_msg, False)

    friends_list[sender].chats.append(new_chat)

    print ("Your secret message " + secret_msg[1:])

    if secret_msg.upper() in SPECIALMSG:
        print ("SPY ALERT! SPY ALERT! SPECIAL MESSAGE GENERATED: "+secret_msg)


    if(len(secret_msg.split(" "))) > 100:
        print ("Spy friend" +friends_list[sender].name+" spoke too much. His profile will now be terminated!")
        del friends_list[sender]

def read_friend_status():
    friendchoice=select_a_friend()
    print ('friends_list[friendchoice].current_status_message')

def read_friends():
    item_num = 0

    if len(friends_list) != 0:
        for friend in friends_list:
            print ('%d. %s %s aged %d with rating %.2f is online' % (item_num + 1, friend.salutation, friend.name,
                                                                    friend.age,
                                                                    friend.rating))
            item_num = item_num + 1
    else:
        addfrnd = raw_input("No Friend found! Add a friend first (y/n)!")
        if addfrnd[0].upper() == 'Y':
            add_friend()
        else:
            print ("No friends found!")


def read_old_msg():
    frnd_choice=select_a_friend()

    print '\n'
    if len(friends_list[frnd_choice].chats) == 0:
        print 'No previous chats exist.'
    else:
        for chat in friends_list[frnd_choice].chats:

            print '[%s]' % (chat.time.strftime("%d %B %Y %H:%M"))
            if chat.is_sent_by_me:
                print ("%s %s" %('You:', chat.message))
            else:
                print ('%s: %s' % (friends_list[frnd_choice].name,
                                                    chat.message))


def remove_friend():
    frnd_pos=select_a_friend()
    del friends_list[frnd_pos]
    return len(friends_list)

def remove_status():
    ansint=-1
    if len(STATUS_MSGS) != 0:
        itemno=0;
        for msg in STATUS_MSGS:
            print ("%d. %s" %(itemno+1,msg))
            itemno+=1
        ansr = raw_input("Select a status to delete")

        try:
            ansint=int(ansr)
            ansint-=1
        except:
            print ("Wrong input spy! Be smart except")

        if ansint >- 1 and ansint < len(STATUS_MSGS):
            del STATUS_MSGS[ansint]
        else:
            print ("Wrong input spy! Be smart")

    else:
        print ("No status messages found!")

def start_chat(spy):

    spy.name = spy.salutation + " " + spy.name


    if spy.age > 12 and spy.age < 50:


        print ( "Authentication complete. Welcome " + spy.name + " age: " \
              + str(spy.age) + " and rating of: " + str(spy.rating) + " Proud to have you onboard")

        show_menu = True


        while show_menu:
            menu = "Your Spy tools  \n 1. Add a status update \n 2. Add a friend \n 3. Send a secret message " \
                   "\n 4. Read a secret message \n 5. Read Chats from a user \n 6. List all the friends \n "\
                   "7. Remove Friend \n 8. Remove older status  \n 9. Close Application \n"
            menu_choice = raw_input(menu)

            if len(menu_choice) > 0:
                menu_choice = int(menu_choice)

                if menu_choice == 1:
                    spy.current_status_message = add_status_message()
                elif menu_choice == 2:
                    num_of_frnds = add_friend()
                    if num_of_frnds != -1:
                        print 'You have %d friends' % (num_of_frnds)
                elif menu_choice == 3:
                    send_message()
                elif menu_choice == 4:
                    read_message()
                elif menu_choice == 5:
                    read_old_msg()
                elif menu_choice == 6:
                    read_friends()
                elif menu_choice == 7:
                    remove_friend()
                elif menu_choice == 8:
                    remove_status()
                else:
                    print ('Pleasure to assist a world class Spy.')
                    show_menu = False
    else:
        print ('Sorry you are not of the correct age to be a spy')

ques = "Continue as " + spy.salutation + " " + spy.name + " (Y/N)? "
ans = raw_input(ques)

if ans[0].upper() == "Y":
    start_chat(spy)

else:

    spy = Spy('', '', 0, 0.00)

    spy.name = raw_input("SpyChat welcomes you, your spy name please: ")

    if len(spy.name) > 0:
        if spy.name.decode('utf-8').isspace():
            print ('Spy name not valid! Be smart next time spy')
            exit(0)

        spy.salutation = raw_input("Great! Mr. or Ms.?: ")

        if len(spy.salutation) > 0:
            if spy.salutation.decode('utf-8').isspace():
                print ('Spy salutation not valid! Be smart next time spy')
                exit(0)
        spy.age = raw_input("Your age please?")


        try:
            spy.age = int(spy.age)
        except:
            print ("The age has to be numerical Spy! Be smart next time! \n Bye!")
            exit(0)

        spy.rating = raw_input("Your genuine spy rating?")


        try:
            spy.rating = float(spy.rating)
        except:
            print ("The rating has to be numerical Spy! Be smart next time! \n Bye!")
            exit(0)

        start_chat(spy)
    else:
        print ("No nameless spy allowed! Be smart next time! \n Bye!")
        exit(0)
