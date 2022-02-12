import urllib.request
import requests
import json
import itertools
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.animation
import re
 
 
def nice_time(t):  # makes the time nice for the animation
   hours, minutes = divmod(t, 60)
   if minutes != 0:
       if hours > 1:
           return (str(int(hours)) + " hours " + str(int(minutes)) + " minutes")
       if hours == 1:
           return ("1 hour " + str(int(minutes)) + " minutes")
       else:
           return (str(int(minutes)) + " minutes")
   if minutes == 0:
       return (str(int(hours)) + " hours")
 
def walking_route(origin,destination): #finds the walking route between two stations
   MyKey = "AIzaSyDzvRCXujh6NB31Vnf33826Lan75e6gPgs"  # googlemaps api key
 
   def _url(path):  # to save having to use the link each time can use this to save time
       return ("https://maps.googleapis.com/maps/api/directions/json?{}&key={}".format(path, MyKey))
 
   x = requests.get(_url("origin={}&destination={}&mode=walking".format(origin.replace(" ","+") + "Underground+Station,+London", destination.replace(" ","+")+ "Undergorund+Station,+London"))).json()
   distance = 0 #distance in m
   duration = 0 #time in s
   if x['status'] == "ZERO_RESULTS": #include this because sometimes can't find station - for example thnks chalfont and laitmer Underground Station London is in North Carolina
       return(float('inf'),float('inf'),['N/A'])
   legs= x['routes'][0]['legs']
   instructions = []
   for i in legs:
       for step in i['steps']:
           distance += step['distance']['value']
           duration += step['duration']['value']
 
           cleanr = re.compile('<.*?>') #removes html tags to get instructions
           instruction = re.sub(cleanr, '', step['html_instructions']) #adds spaces before capital letters
           re.sub(r"(\w)([A-Z])", r"\1 \2", instruction)
           instructions.append(instruction + ", go " + str(step['distance']['value']) + " metres")
 
   return(int(duration/60),distance/1600,instructions) #time in minutes, distance in miles, instructions
 
def tsp_route(speed_of_user,max_user_distance,calculation_speed,nostations,toutput):
 
   max_user_distance /= 69 #converts to coordinates
   speed_of_user /= 69 * 60 #converts to coordinates per minute
 
   lines = pd.read_csv('london.lines.csv',index_col=0) #reads the csv gets a list of lines
   stations = pd.read_csv('london.stations.csv', index_col=0) #reads the csv to get a list of stations
   connections = pd.read_csv('london.connections.csv') #reads the csv to get a list of stations
 
   if nostations == "normal": #this removes all connections that are DLR/East London Line
       connections_todrop = connections[(connections['line']==13) | (connections['line'] == 5)]
       connections.drop(connections_todrop.index,inplace = True)
 
 
   stations.sort_values('id')
   stations['lines'] = 0#adds a line column to the stations dataframe
   stations['lines'] = stations['lines'].astype(object)
   station_lines = {}
 
   graph = nx.Graph()
 
   for connection_id, connection in connections.iterrows(): #Gets a list of lines that each station is on and adds the connections to the graph
 
       station1 = stations.loc[connection['station1']]
       station2 = stations.loc[connection['station2']]
 
       station1_name = station1['name']
       station2_name = station2['name']
 
       if station1_name in station_lines:
           station_lines[station1_name].append(connection['line'])
           station_lines[station1_name] = list(dict.fromkeys(station_lines[station1_name]))
       elif station1_name not in station_lines:
           station_lines[station1_name] = [connection['line']]
 
       if station2_name in station_lines:
           station_lines[station2_name].append(connection['line'])
           station_lines[station2_name] = list(dict.fromkeys(station_lines[station2_name]))
       elif station2_name not in station_lines:
           station_lines[station2_name] = [connection['line']]
 
 
       graph.add_edge(station1_name, station2_name, time=connection['time'])
 
 
   #add the connection between Bank and Monument manually as it is a walking route
 
   graph.add_edge('Bank', 'Monument', time=1)
   for key,value in station_lines.items(): #adds the lines that the stations are on
       pos = int((stations[stations['name']==key].index.values)[0])
       stations.at[pos,'lines'] = value
 
   stationstodrop = stations[stations['lines'] == 0].index #removes stations that aren't connected to anything
   stations.drop(stationstodrop,inplace= True)
 
   sol = {x:[] for x in range(1,len(lines.index)+1)} #list of stations on each line
   for index,station in stations.iterrows():
       for i in station['lines']:
           sol[i].append(index)
 
   end_nodes = []
   for i in graph: #creates a list of end nodes
       if len(graph.edges(i)) == 1:
           end_nodes.append(i)
 
   for i in end_nodes:
       pos = int((stations[stations['name']==i].index.values)[0]) #index of end node
       on_lines = stations.loc[pos]['lines'] #line the end node is on
       coords = [stations.loc[pos]['latitude'],stations.loc[pos]['longitude']] #coordinates of the stations
       min_list = [] #list of closest statino on each line
       for key,values in sol.items(): #goes through dictionary which contains which stations are on which lines
           min_distance = float('inf')
           if key not in on_lines: #makes it so that can not connnect to stations on the same line
               for j in values: #goes through each station on that line
                   coords2 = [stations.loc[j]['latitude'],stations.loc[j]['longitude']] #gets coordinates of the other station
                   distance = ((coords[0]-coords2[0])**2+(coords[1]-coords2[1])**2)**0.5 #finds distance
                   if distance < min_distance: #if this is the closest one make this the station that it can connect to
                       min_distance = distance
                       closest = [j,distance]
               min_list.append([stations.loc[closest[0]]['name'],closest[1]]) #gets the closet station on each line to the end node
 
       overground_connections = {x: [] for x in end_nodes}  # creates a list of overground conections
 
       instructions_dict = {}  # creates a dictinoary of the overground routes
       for j in min_list: #potential stations that the end node can connect to
           if speed_of_user != 0:
               if calculation_speed == "accurate": #use google maps
                   r = walking_route(i,j[0]) #finds the route
                   if r[1] < max_user_distance*69: #converts into coordinates
                       overground_connections.setdefault(i, []).append(j[0])
                       graph.add_edge(i,j[0],time = (r[1]/speed_of_user))
                       instructions_dict[i] = [j[0],r[2]]
                       instructions_dict[j[1]] = [i,r[2]]
               if calculation_speed == "fast": #as the crow flies
                   if distance < max_user_distance:
                       overground_connections.setdefault(i, []).append(j[0])
                       graph.add_edge(i,j[0],time = (distance/speed_of_user))
 
   pos = {}
   for i in graph:
       p = int((stations[stations['name']==i].index.values)[0])
       lat = stations.loc[p]['latitude']
       long = stations.loc[p]['longitude']
       pos[i] = (long,lat)
 
   floyd = nx.Graph()
   f = nx.floyd_warshall(graph)
   for stat,con in f.items():
       for key,values in con.items():
           floyd.add_edge(stat,key,time = values)
 
   def find_route(start_node): #goes around the floyd warhsall and does a greedy alogrithm to find a route
       route = [start_node]
       time  = 0
       timing = []
       unvisited = [x for x in graph] #remove from unvisited start_node
       unvisited.remove(start_node)
       current = start_node
       while len(unvisited)!=0:
           potential = f[current]
           min = float('inf')
           for key,values in potential.items():
               if values < min and key in unvisited:
                   next = key
                   min  = values
           path = nx.shortest_path(graph,source = current,target = next)
           l = len(path)-1
           for i in path[1:]:
               time += min * 2 /l
               timing.append(time)
               route.append(i)
               if i in unvisited:
                   unvisited.remove(i)
           current = next
       return(time,route,timing)
 
   list_of_routes = {} #goes through each station and computes the time to go around, then returns the shortest one
 
   for i in f: #finds routes starting at each station and returns the one that is the shortest
       list_of_routes[i] = find_route(i)[0]
   shortest = min(list_of_routes,key = list_of_routes.get)
   p = find_route(shortest)[1]
 
   def get_instructions(o,d): #goes through each station checks if there is an over ground connection possible and if there is outputs the text instructions
       o_start = [values for x,values in instructions_dict.items() if x == o]
       d_start = [values for x,values in instructions_dict.items() if x == d]
       for i in o_start:
           if i[0] == d:
               return(i[1])
       for i in d_start:
           if i[0] == o:
               return(i[1])
       return(False)
 
   def text_output():
       output = []
       for pos,i in enumerate(p[:-1]): #goes through all stations
           words = get_instructions(i,p[pos+1]) #checks if the stations are connected overground
           output.append(i)
           if words != False: #if the stations are connected overground the instructions
               output.append(words)
       output.append(p[-1]) #add the final station
       return(output)
 
   def animation(): #animates the route
       fig, ax = plt.subplots(figsize=(6, 4)) #sets the size of the animation
 
       def update(num):
           ax.clear() #removes the axis
           path = p[:num] #path up until the current step
 
           nx.draw_networkx_edges(graph, pos=pos, ax=ax, edge_color="gray") #this is the settings for the nodes that aren't animated
           null_nodes = nx.draw_networkx_nodes(graph, pos=pos, nodelist=set(graph.nodes()) - set(path), node_color="white",node_size=10,ax=ax)
           null_nodes.set_edgecolor("black")
 
           path_nodes = nx.draw_networkx_nodes(graph, pos=pos, nodelist=path, node_color="red",node_size=10, ax=ax) #this is the setting for the nodes that are animated
           path_nodes.set_edgecolor("red")
           edgelist = [path[k:k + 2] for k in range(len(path) - 1)] #goes  through the list of nodes and chooses which one should be drawn
           nx.draw_networkx_edges(graph, pos=pos, edgelist=edgelist, ax=ax)
           if num > 1:
               ax.set_title(path[num-1] + " " + nice_time(find_route(shortest)[2][num-1])) #writes the title
 
       ani = matplotlib.animation.FuncAnimation(fig, update, frames=len(p), interval=50, repeat=True)
       plt.show()
 
       #ani.save('TSProute50.gif', writer='imagemagick', fps=60) #creating gif
   animation()
 
   if toutput == True:
       print("With a user speed of {} mph and a maximum distance of {} miles, the total journey time is {}".format(int(speed_of_user*69*60),int(max_user_distance*69),nice_time(find_route(shortest)[2][-1])))
       print(text_output())
