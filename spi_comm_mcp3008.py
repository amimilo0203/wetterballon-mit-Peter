import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BOARD)
GPIO.setup(24, GPIO.OUT) #pin 24 is chip enable
GPIO.setup(23, GPIO.OUT) #pin 23 is clock
GPIO.setup(19, GPIO.OUT) #pin 19 is data out
GPIO.setup(21, GPIO.IN) #pin 21 is data in
#set pins to default state
GPIO.output(24, True)
GPIO.output(23, False)
GPIO.output(19, True)

#set address chanels 0 to 7
#1st bit selects single/differential
#2nd, 3rd, 4th bit channel address
#5th bit 1 bit delay for data
#6th bit 1st null bit of data


# if channel == 0:
# 	word= [1, 1, 0, 0, 0, 1, 1]
# if channel == 1:
#	word= [1, 1, 0, 0, 1, 1, 1]

while True:
	word=[1, 1, 0, 0, 0, 1, 1] #set channel to 0
	GPIO.output(24, False) #enable chip
	anip=0 #clear variable
	for x in range (0, 7):
		GPIO.output(19, word[x])
		time.sleep(0.0001)
		GPIO.output(23, True)
		time.sleep(0.0001)
		GPIO.output(23, False)
	#clock in 11 bits of data
	for x in range (0, 12):
		GPIO.output(23, True) #set clock hi
		time.sleep(0.0001)
		bit=GPIO.input(21) #read input
		time.sleep(0.0001)
		GPIO.output(23, False) #set clock low
		value=bit*2**(12-x-1) #work out value of this bit
		anip=anip+value #add to previous total
	print (anip)
	GPIO.output(24, True)
