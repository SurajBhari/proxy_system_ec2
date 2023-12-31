from ec2_proxy import TProxy
import boto3
import config
import threading
import time
import create_new

class Manager:
    def __init__(self) -> None:
        ec2_resource = boto3.resource('ec2', 
                                      region_name=config.Credentials.region, 
                                      aws_access_key_id=config.Credentials.key, 
                                      aws_secret_access_key=config.Credentials.secret
                                      )
        ec2 = boto3.client('ec2', 
                           region_name=config.Credentials.region, 
                           aws_access_key_id=config.Credentials.key, 
                           aws_secret_access_key=config.Credentials.secret
                           )    
        nodes = []
        response = ec2.describe_instances()
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                if instance['InstanceId'] not in config.Exclusions.ids:
                    nodes.append(instance['InstanceId'])
        # start the nodes if they are not running
        for node in nodes:
            try:
                TProxy(instance_id=node, ec2=ec2).start()
            except:
                pass
        self.ec2_resoruce = ec2_resource
        self.nodes = nodes
        self.ec2 = ec2
        self.in_use = []
        self.to_restart = []
        self.__start_auto_method()

    def make_new_proxy(self):
        new_instance_id = create_new.create(self.ec2_resoruce, config.Extras.image_id)
        self.nodes.append(new_instance_id)
        return new_instance_id
        
    def serve(self, old_instance_ip=""):
        old_instance_id = ""
        if old_instance_ip:
            for instance_id in self.in_use:
                if TProxy(instance_id=instance_id, ec2=self.ec2).get_current_ip() == old_instance_ip:
                    old_instance_id = instance_id
                    break

        if len(self.nodes) == 0:
            return None
        new_instance_id = self.nodes.pop()
        self.in_use.append(new_instance_id)
        if old_instance_id:
            self.to_restart.append(old_instance_id)
        # return the public ip of the new instance
        response = self.ec2.describe_instances(InstanceIds=[new_instance_id])
        return response['Reservations'][0]['Instances'][0]['PublicIpAddress']
    
    def cleanup(self):
        print("Cleaning up")
        for instance_id in self.to_restart:
            TProxy(instance_id=instance_id, ec2=self.ec2).restart()
        self.to_restart = []
        threading.Timer(60, self.cleanup).start()

    def __start_auto_method(self):
        threading.Timer(0, self.cleanup).start()
    
    def delete_node(self, instance_id):

        self.nodes.remove(instance_id)
        self.ec2.terminate_instances(InstanceIds=[instance_id])
        if instance_id in self.in_use:
            self.in_use.remove(instance_id)
        if instance_id in self.to_restart:
            self.to_restart.remove(instance_id)

        return instance_id

    def len_available(self):
        return len(self.nodes)
    
    def get_available(self):
        return self.nodes

    def restart_all(self):
        for instance_id in self.nodes:
            self.to_restart.append(instance_id)
            self.nodes.remove(instance_id)
        self.cleanup()
    
    def shutdown_all(self):
        for instance_id in [*self.nodes, *self.in_use, *self.to_restart]:
            self.ec2_resource.Instance(instance_id).stop()
            self.nodes.remove(instance_id)
            if instance_id in self.in_use:
                self.in_use.remove(instance_id)
            if instance_id in self.to_restart:
                self.to_restart.remove(instance_id)

if __name__ == "__main__":
    manager = Manager()
    for node in manager.nodes:
        print("Deleting node", node)
        manager.delete_node(node)
    print(manager.len_available())
    print(manager.get_available())
    if manager.len_available() < 3:
        for x in range(3 - manager.len_available()):
            manager.make_new_proxy()
    ip = manager.serve()
    for x in range(10):
        ip = manager.serve(ip)
        print(ip)
        time.sleep(15)
    manager.shutdown_all()
    for node in manager.nodes:
        manager.delete_node(node)

    

