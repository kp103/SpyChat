from datetime import datetime

class Spy:

    def __init__(self, name, salutation, age, rating):
        self.name = name
        self.salutation = salutation
        self.age = age
        self.rating = rating
        self.is_online = True
        self.chats = []
        self.current_status_message = "Hey there I am using spyChat!"

class ChatMessage:

    def __init__(self,message,sent_by_me):
        self.message = message
        self.time = datetime.now()
        self.is_sent_by_me = sent_by_me

spy = Spy('Bond', 'Mr.', 23, 4.0)

frnd_one = Spy('Shubham', 'Mr.', 27, 4.03)
frnd_two = Spy('Mohit', 'Mr.', 21, 4.24)
frnd_three = Spy('Akshay', 'Mr.', 34, 4.34)


friends_list = [frnd_one, frnd_two, frnd_three]