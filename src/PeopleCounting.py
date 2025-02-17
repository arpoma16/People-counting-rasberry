from threading import Thread
import numpy as np
import cv2
import time
import os

import mqtt_publish
from argparser import Argparser
import telegramBoot
from Person import MyPerson,blobles
from VideoGet import VideoStream

defaults = {
		"platform": os.name,
		"path": os.getcwd(),
		"file_in":"../data/Video_example01.mp4"
}


maxpeople=2
frame = 0
bid =0
pid = 1 #id de la persona 
max_p_age = 10
persons = []
burbles = []
fgbg = cv2.createBackgroundSubtractorMOG2(history = 3000, varThreshold = 60,detectShadows = True)

kernelOp = np.ones((5,5),np.uint8)
kernelCl = np.ones((20,20),np.uint8)

color = ('b','g','r')
font = cv2.FONT_HERSHEY_SIMPLEX
predictedCoords = np.zeros((2, 1), np.float32)
colors = [tuple(255 * np.random.rand(3)) for _ in range(10)]

overpeople_cascade = cv2.CascadeClassifier('..//data//People_detector.xml')

line_down_color = (255,0,0)
line_up_color = (0,0,255)


class Peoplecount:

    def __init__(self,args):
        self.init= True
        self.VideoStream_obj = None
        self.img_stream_send = None
        self.h=0
        self.w=0
        self.stopped = False
        self.maxpeople = 2
        self.countup = 0
        self.countdown = 0
        self.countuplast = 0
        self.countdownlast = 0

        if args["source"][0]=="file" or args["source"][0]=="ipcamera":## ip camera y file es igual
            print("[INFO] Starting the video ... "+ args['file_in'])
            self.VideoStream_obj = VideoStream(src=args['file_in']).start()

        if args["source"][0]=="picamera":
            print("[INFO] streaming the video  from picamera ok")
            self.VideoStream_obj = VideoStream(usePiCamera=True,src=args['file_in']) .start()

        if args["source"][0]=="usbcamera":
            print("[INFO] Starting usb camera")
            self.VideoStream_obj = VideoStream(src=0).start()

        time.sleep(2)

        telegramBoot.telegram_DeviceOn()
        mqtt_publish.publish_people_in_single(self.countup)
        mqtt_publish.publish_people_out_single(self.countdown)
        mqtt_publish.publish_people_into_single(self.countup-self.countdown)

        self.grabbed, img_get = self.VideoStream_obj.getframe()
        self.h = img_get.shape[0]
        self.w = img_get.shape[1]
        print(img_get.shape)
        


    def update_count(self):

        if self.countdown != self.countdownlast or self.countup !=self.countuplast:
            print("contador de entrada")
            mqtt_publish.publish_people_into_single(self.countup-self.countdown)
            if (self.countup-self.countdown)>self.maxpeople:
                print("Telegram alarm --Full send each minute")
                telegramBoot.telegram_Devicefull(self.countup-self.countdown)

        if self.countup !=self.countuplast :
            print("diferencia de contador de subida")
            mqtt_publish.publish_people_in_single(self.countup)
            self.countuplast = self.countup 

        if self.countdown != self.countdownlast:
            print("difenrencia de contador de salida")
            mqtt_publish.publish_people_out_single(self.countdown)
            self.countdownlast = self.countdown

    def getcount(self):
        return (self.countup,self.countdown)

    def PeopleCounter(self,cap_img,areaTH):
        global frame,pid,bid,max_p_age
        global persons,burbles,fgbg
        img=cv2.GaussianBlur(cap_img,(3,3),cv2.BORDER_DEFAULT)
        imgw=self.w
        imgh=self.h
        line_down =int(self.h/2)
        line_up = int(self.h/2) 

        frame += 1

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        for i in persons:
            i.age_one()# edad de la persona en un img  age = 1

        #aplicacion del background sustraction
        fgmask2 = fgbg.apply(img)
        #backGnd = fgbg.getBackgroundImage() # fondo
        #Binariazcion para eliminar sombras (color gris)
        ret,imBin2 = cv2.threshold(fgmask2,200,255,cv2.THRESH_BINARY)
        #Opening (erode->dilate) para quitar ruido.
        mask2 = cv2.morphologyEx(imBin2, cv2.MORPH_OPEN, kernelOp)
        #Closing (dilate -> erode) para juntar regiones blancas.
        mask2 = cv2.morphologyEx(mask2, cv2.MORPH_CLOSE, kernelCl)

        contours0, hierarchy = cv2.findContours(mask2,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)

        thresh = cv2.merge((mask2,mask2,mask2))
        res = cv2.bitwise_and(cap_img,thresh)

        exist = True
        for cnt in contours0:
            area = cv2.contourArea(cnt)
            x,y,w,h = cv2.boundingRect(cnt)

            if area > areaTH and w > 50 and h > 50:
                newblob = True 
                for blob in burbles:
                    #if  
                    newblob = False

                if newblob == True:
                    b = blobles(bid,x,y,w,h,10)
                    burbles.append(b)# pone  en la ultima posicion
                    bid += 1 

                # si dos borbujas estan cerca y tienen el mismo color 
                # tomar encuanta burbujar con un w>50 h>50
                exist = False
                #cv2.rectangle(img,(x,y),(x+w,y+h),(0,255,0),2)
                #cv2.circle(img,(int(x+w/2),int(y+h/2)), 5, (0,255,0), -1)
            else:
                cv2.rectangle(mask2,(x,y),(x+w,y+h),(0),-1)
        if exist:
            #print('NO CONTORNO')
            for blob in burbles:
                index = burbles.index(blob) #devielve la posicion del objeto
                burbles.pop(index) #Elimina el objeto de la  index 
                del blob

        ## detección

        ## darle algo mas pequeño para que pueda determinar si es o no es una persona.

        results = overpeople_cascade.detectMultiScale(gray, 7, 5)
        if ret:
            for (color, result) in zip(colors, results):#obtiene la poscicion de los haarcascade encontrados 
                (x,y,w,h) = result
                cx = int(x + w / 2)
                cy = int(y + h / 2)
                bbox = (x, y, w, h) 

                if w > 50:
                    new = True
                    if cy in  range (line_down-200,line_up+200):
                        for i in persons:
                            if  i.getX()  in range(x, x+w) and i.getY()  in range(y, y+h):
                                #print("actualiza cordenadas id: " ,i.getId(),"bbox", bbox)
                                new = False
                                i.updateCoords(cx,cy)# age = 0
                                predictedCoords = i.prediction()
                                #print("predicted Coords"+str(predictedCoords))
                                cv2.circle(img, (int(predictedCoords[0]), int(predictedCoords[1])), 20, (0,255,255), 2, 8)
                                break
                            if len(i.getTracks()) >= 2:
                                print("conteo i.getY()"+str(i.getY())+"  ----- getTracks" +str(i.getTracks()[0][1]))
                                if (i.getY() > line_up) and  i.getUp(30,False) and (i.getTracks()[0][1])<line_up:
                                    self.countup +=1
                                    i.setDone()
                                if (i.getY() < line_down) and  i.getDown(30,False) and (i.getTracks()[0][1])>line_down :
                                    self.countdown +=1
                                    i.setDone()
                            if i.timedOut():#return done 
                                index = persons.index(i) #devielve la posicion del objeto
                                persons.pop(index) #Elimina el objeto de la  index 
                                print('timedOut1:  ',i.getId())
                                del i
                        if new == True:
                            p = MyPerson(pid,cx,cy, max_p_age)
                            persons.append(p)# pone  en la ultima posicion
                            pid += 1 
                    # muestra las detecciones por el  haar cascade
                    cv2.circle(img,(cx,cy), 5, (0,0,255), -1)
                    cv2.rectangle(img,(x,y),(x+w,y+h),(255,0,0),2)
                    # persona dentro de la zona de interez

        for i in persons:
            
            if len(i.getTracks()) >= 2:
                print( "id:"+str(i.getId()) +"-"+ str(i.getDown(30,False)) +"-"+ str(i.getUp(30,False))+"conteo i.getY()"+str(i.getY())+"conteo i.getx()"+str(i.getX())+" init" +str(i.getTracks()[0][1]))
                pts = np.array(i.getTracks(), np.int32)
                pts = pts.reshape((-1,1,2))
                img = cv2.polylines(img,[pts],False,i.getRGB())
            cv2.putText(img, str(i.getId()),(i.getX(),i.getY()),font,0.3,i.getRGB(),1,cv2.LINE_AA)
            if i.getAge() > 0 :# buscar la  burbuja que lo pueda contener y actualizar su punto con tracking  con el movimiento relativo de la burbuja
                predictedCoords = i.predict()
                cv2.circle(img, (int(predictedCoords[0]), int(predictedCoords[1])), 20, [255,0,255], 2, 8)
                #i.updateCoords(predictedCoords[0], predictedCoords[1])
                posi = False
                exist = False
                for cnt in contours0:
                    area = cv2.contourArea(cnt)
                    x,y,w,h = cv2.boundingRect(cnt)
                    if area > areaTH and w > 50 and h > 50:
                        if  i.getX()  in range(x, x+w) and i.getY()  in range(y, y+h):
                            posi = True
                            i.updateCoords(x+w/2,y+h/2)

                if exist or posi:
                    if len(i.getTracks()) >= 2:
                        print("111conteo i.getY()"+str(i.getY())+"  --- -- getTracks" +str(i.getTracks()[0][1]))
                        if (i.getY() > line_up) and  i.getUp(30,False) and (i.getTracks()[0][1])<line_up:
                            self.countup +=1
                            i.setDone()
                        if (i.getY() < line_down) and  i.getDown(30,False) and (i.getTracks()[0][1])>line_down :
                            self.countdown +=1
                            i.setDone()
                    index = persons.index(i) #devielve la posicion del objeto
                    persons.pop(index) #Elimina el objeto de la  index 
                    #print('timedOut2:  ',i.getId())
                    del i

        #  creacion de las lineas
        pt1 =  [ 0, line_down];
        pt2 =  [ imgw, line_down];
        pts_L1 = np.array([pt1,pt2], np.int32)
        pts_L1 = pts_L1.reshape((-1,1,2))

        pt3 =  [ 0, line_up];
        pt4 =  [ imgw, line_up];
        pts_L2 = np.array([pt3,pt4], np.int32)
        pts_L2 = pts_L2.reshape((-1,1,2))
        img = cv2.polylines(img,[pts_L1],False,line_down_color,thickness=2)
        img = cv2.polylines(img,[pts_L2],False,line_up_color,thickness=2)
        
        # mostrar valores
        str_up = 'P.Entrado: '+ str(self.countup)
        str_down = 'P.Salido: '+ str(self.countdown)
        cv2.putText(img, str_up ,(10,40),font,0.5,(0,0,255),1,cv2.LINE_AA)
        cv2.putText(img, str_down ,(10,90),font,0.5,(255,255,255),2,cv2.LINE_AA)

        self.img_stream_send = img# cv2.hconcat([img, res])
        self.update_count()
        #cv2.imshow('uno', img)

    def stop(self):
        self.stopped = True

    def update(self):
        areaTH = 1228.8
        while not self.stopped:
            try:
                if not self.grabbed:
                    self.stop()
                else:
                    self.grabbed ,img_get  = self.VideoStream_obj.getframe()
                    if self.grabbed:
                        self.PeopleCounter(cap_img = img_get,areaTH=areaTH)
                        #k = cv2.waitKey(1) & 0xFF
                        #if k == 27:   # hit escape to quit
                        #    break
            except AttributeError:
                pass
        
        self.VideoStream_obj.stop()

    def start(self):
        Thread(target=self.update, args=()).start()
        return self

    def getimage(self):
        return self.img_stream_send

if __name__ == "__main__":
    #cv2.namedWindow('uno')
    args = Argparser(defaults)
    print(args)
    print(args["source"])
    peopleobj = Peoplecount(args)
    peopleobj.update()

    
