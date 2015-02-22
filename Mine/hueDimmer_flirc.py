from evdev import InputDevice
import time, select, requests, json


POWER = 458796
TEMP_UP = 458775
TEMP_DOWN = 458780
BRIGHTNESS_UP = 458757
BRIGHTNESS_DOWN = 458769


max_brightness = 255
min_brightness = 0
brightness_step = 10
max_colortemp = 500 # equivalent of 2000K
min_colortemp = 153 # equivalent of 6500K
colortemp_step = 20


success = 200 # http response code

# The following values must be set according to your setup
ip = '192.168.1.6'

# you must have created a user named newdevolper, as per the instructions at http://developers.meethue.com/gettingstarted.html
url = 'http://' + ip + '/api/newdeveloper/groups/0/'



def toggle_all():
    g = requests.get(url)
    if g.status_code == success:
        on = json.loads(g.content)['action']['on']
        
        if on == False:
            hour = time.localtime().tm_hour
            ct = max_colortemp
            bri = min_brightness
            if hour >= 5 and hour <= 11:
                ct = min_colortemp
                bri = max_brightness
            elif hour >= 12 and hour <= 17:
                ct = 250
                bri = max_brightness
            elif hour >= 18 and hour <= 20:
                ct = 400
                bri = 150
            elif hour >= 21 and hour <= 23:
                ct = max_colortemp
                bri = 50
            #print "bri = " + str(bri) + " ct = " + str(ct) + " hour = " + str(hour)
            p = requests.put(url + "action", data=json.dumps({"on":True, "bri":bri, "ct":ct, "transitiontime":2}))
        else:
            p = requests.put(url + "action", data=json.dumps({"on":False, "transitiontime":2}))


def main():
    dev = InputDevice("/dev/input/by-id/usb-flirc.tv_flirc-event-kbd")
    while True:
        r,w,x = select.select([dev], [], [])
        e = dev.read_one()
        if e.code == 125 and e.value == 1:
            e = dev.read_one()
            g = requests.get(url)

            if e.value == POWER:
                toggle_all()


            elif e.value == TEMP_DOWN:
                ct = json.loads(g.content)['action']['ct']

                if ct == max_colortemp:
                    continue
                elif ct + colortemp_step > max_colortemp:
                    ct = max_colortemp
                else:
                    ct = ct + colortemp_step

                p = requests.put(url + "action", data=json.dumps({"ct": ct, "transitiontime":2}))


            elif e.value == TEMP_UP:
                ct = json.loads(g.content)['action']['ct']

                if ct == min_colortemp:
                    continue
                elif ct - colortemp_step < min_colortemp:
                    ct = min_colortemp
                else:
                    ct = ct - colortemp_step

                p = requests.put(url + "action", data=json.dumps({"ct": ct, "transitiontime":2}))


            elif e.value == BRIGHTNESS_UP:
                bri = json.loads(g.content)['action']['bri']

                if bri == max_brightness:
                    continue
                elif bri + brightness_step > max_brightness:
                    bri = max_brightness
                else:
                    bri = bri + brightness_step

                p = requests.put(url + "action", data=json.dumps({"bri": bri, "transitiontime":2}))


            elif e.value == BRIGHTNESS_DOWN:
                bri = json.loads(g.content)['action']['bri']

                if bri == min_brightness:
                    continue
                elif bri - brightness_step < min_brightness:
                    bri = min_brightness
                else:
                    bri = bri - brightness_step

                p = requests.put(url + "action", data=json.dumps({"bri": bri, "transitiontime":2}))
                
if __name__ == "__main__":
    main()
