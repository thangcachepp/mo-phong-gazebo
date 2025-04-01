#!/usr/bin/env python3
import rospy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64
import sys, select, termios, tty

# Cài đặt tốc độ và góc quay (tăng tốc độ để xe chạy nhanh hơn)
MAX_LIN_VEL = 150.0 # m/s (tăng tốc độ tuyến tính)
MAX_ANG_VEL = 150.0 # rad/s (tăng tốc độ góc)
LIN_VEL_STEP = 50  # Bước thay đổi tốc độ tuyến tính (tăng tốc độ thay đổi)
ANG_VEL_STEP = 50  # Bước thay đổi tốc độ góc (tăng tốc độ thay đổi)

# Cài đặt tốc độ cho các khớp tay máy
MAX_JOINT_VEL = 150  # rad/s
JOINT_VEL_STEP = 50  # Bước thay đổi tốc độ khớp

msg = """
Điều khiển xe robot bằng bàn phím:
---------------------------
Di chuyển:
    w
a   s   d
    x

w/x: tăng/giảm tốc độ tiến/lùi
a/d: tăng/giảm tốc độ rẽ trái/phải
s: dừng xe

Điều khiển tay máy:
    i   k: tăng/giảm tốc độ khớp tay máy
    j   l: quay trái/quay phải khớp tay máy

Nhấn Ctrl+C để thoát
"""

class KeyboardControl:
    def __init__(self):
        rospy.init_node('keyboard_control')
        
        # Publisher cho cmd_vel
        self.cmd_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
        
        # Publisher cho các khớp tay máy
        self.link1_pub = rospy.Publisher('/link1_joint_controller/command', Float64, queue_size=10)
        self.link2_pub = rospy.Publisher('/link2_joint_controller/command', Float64, queue_size=10)
        
        self.settings = termios.tcgetattr(sys.stdin)
        self.twist = Twist()
        self.target_linear_vel = 0.0
        self.target_angular_vel = 0.0
        self.current_linear_vel = 0.0
        self.current_angular_vel = 0.0

        # Biến cho tốc độ các khớp tay máy
        self.link1_vel = 0.0
        self.link2_vel = 0.0
    
    def get_key(self):
        tty.setraw(sys.stdin.fileno())
        rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
        if rlist:
            key = sys.stdin.read(1)
        else:
            key = ''
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.settings)
        return key
    
    def constrain(self, input, low, high):
        return min(max(input, low), high)
    
    def check_linear_limit_velocity(self, vel):
        return self.constrain(vel, -MAX_LIN_VEL, MAX_LIN_VEL)
    
    def check_angular_limit_velocity(self, vel):
        return self.constrain(vel, -MAX_ANG_VEL, MAX_ANG_VEL)
    
    def print_vels(self):
        print("Hiện tại: tốc độ tuyến tính %.2f m/s, tốc độ góc %.2f rad/s" % 
              (self.target_linear_vel, self.target_angular_vel))
    
    def print_joint_vels(self):
        print("Tốc độ khớp tay máy: link1: %.2f rad/s, link2: %.2f rad/s" % (self.link1_vel, self.link2_vel))
    
    def run(self):
        print(msg)
        while not rospy.is_shutdown():
            key = self.get_key()
            
            # Xử lý phím điều khiển di chuyển robot
            if key == 'w':
                self.target_linear_vel = self.check_linear_limit_velocity(
                    self.target_linear_vel + LIN_VEL_STEP)
                self.print_vels()
            elif key == 'x':
                self.target_linear_vel = self.check_linear_limit_velocity(
                    self.target_linear_vel - LIN_VEL_STEP)
                self.print_vels()
            elif key == 'a':
                self.target_angular_vel = self.check_angular_limit_velocity(
                    self.target_angular_vel + ANG_VEL_STEP)
                self.print_vels()
            elif key == 'd':
                self.target_angular_vel = self.check_angular_limit_velocity(
                    self.target_angular_vel - ANG_VEL_STEP)
                self.print_vels()
            elif key == 's':
                self.target_linear_vel = 0.0
                self.target_angular_vel = 0.0
                self.print_vels()
            
            # Xử lý phím điều khiển tay máy
            elif key == 'i':  # Tăng tốc độ khớp tay máy
                self.link1_vel = min(self.link1_vel + JOINT_VEL_STEP, MAX_JOINT_VEL)
                self.link2_vel = min(self.link2_vel + JOINT_VEL_STEP, MAX_JOINT_VEL)
                self.print_joint_vels()
            elif key == 'k':  # Giảm tốc độ khớp tay máy
                self.link1_vel = max(self.link1_vel - JOINT_VEL_STEP, -MAX_JOINT_VEL)
                self.link2_vel = max(self.link2_vel - JOINT_VEL_STEP, -MAX_JOINT_VEL)
                self.print_joint_vels()
            elif key == 'j':  # Quay trái tay máy (giảm tốc độ khớp)
                self.link1_vel = max(self.link1_vel - JOINT_VEL_STEP, -MAX_JOINT_VEL)
                self.link2_vel = max(self.link2_vel - JOINT_VEL_STEP, -MAX_JOINT_VEL)
                self.print_joint_vels()
            elif key == 'l':  # Quay phải tay máy (tăng tốc độ khớp)
                self.link1_vel = min(self.link1_vel + JOINT_VEL_STEP, MAX_JOINT_VEL)
                self.link2_vel = min(self.link2_vel + JOINT_VEL_STEP, MAX_JOINT_VEL)
                self.print_joint_vels()
            
            else:
                if key == '\x03':  # Ctrl+C để thoát
                    break
            
            # Tạo thông điệp Twist cho robot
            self.twist.linear.x = self.target_linear_vel
            self.twist.angular.z = self.target_angular_vel
            
            # Gửi lệnh điều khiển robot
            self.cmd_pub.publish(self.twist)
            
            # Gửi lệnh điều khiển tay máy
            self.link1_pub.publish(self.link1_vel)
            self.link2_pub.publish(self.link2_vel)
            
        # Dừng xe khi thoát
        self.twist.linear.x = 0.0
        self.twist.angular.z = 0.0
        self.cmd_pub.publish(self.twist)
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.settings)

if __name__ == '__main__':
    try:
        kc = KeyboardControl()
        kc.run()
    except rospy.ROSInterruptException:
        pass
