import logging
from operator import itemgetter
COST_CO2_PER_MWH=0.3 # global variable of cost in CO2

class Process():
    def __init__(self,payload):

        self.payload=payload
        self.cost_co2=payload["fuels"]["co2(euro/ton)"]
        self.cost_gas=payload["fuels"]["gas(euro/MWh)"]
        self.cost_kerosine=payload["fuels"]["kerosine(euro/MWh)"]
        self.wind=payload["fuels"]["wind(%)"]
        self.load=payload["load"]
        self.powerplants=payload["powerplants"]

    def process(self):
        # Logs the received payload
        logging.info("Received payload")
        logging.info(self.payload)
        # Checks the payload integrity
        self.perform_checks()
        #creates the merite order
        order=self.sort_plant_types()
        #creates the solution
        res=self.generate_power(order)
        logging.info("Payload solved")
        logging.info(res)
        return res

    def perform_checks(self):
        """
        Checks for integrity of payload
        Raises excpetion if not working
        """
        try:
            max_fuel = 0
            needed_fuel = self.load
            min_fuel = 0
            too_small_load=True
            for powerplant in self.powerplants:
                if powerplant["pmin"]<needed_fuel:
                    too_small_load=False
                if powerplant["pmin"]>powerplant["pmax"]:
                    logging.error("pmin higher than pmax")
                    raise
                if powerplant["pmin"]<0 or powerplant["pmax"]<0 or powerplant["efficiency"]<0:
                    logging.error("pmin, pmax and efficiency values cannot be negative")
                    raise
                if powerplant["type"] != "windturbine":
                    max_fuel+=powerplant["pmax"]
                    min_fuel+=powerplant["pmin"]
                else:
                    max_fuel+=((powerplant["pmax"]*self.wind)/100)
                    min_fuel += ((powerplant["pmin"] * self.wind) / 100)
            if needed_fuel>max_fuel:
                logging.error("Not enough fuel to fulfil the needed quantity")
                raise
            if too_small_load:
                logging.error("Load to achieve is too small for those plants")
                raise
        except:
            raise ValueError("Incorrect values")

    def sort_plant_types(self):
        """
        creates merite order based on price and efficiency
        :return: list ordered by cheapest production
        """
        cost_gas_co2=self.cost_gas+(COST_CO2_PER_MWH*self.cost_co2) #taking co2 in account
        cost_dict={"windturbine":0,"turbojet":self.cost_kerosine,"gasfired":cost_gas_co2} #dict of prices
        sorted_plants=[]
        for powerplant in self.powerplants:
            cost_per_pwh=cost_dict[powerplant["type"]]/powerplant["efficiency"] #price is influenced by efficiency
            if powerplant["type"]=="windturbine":
                #if it's wind, pmin and pmax values are depending on wind
                factor=self.wind/100
            else:
                #if not wind, then we multiply by 1 -> do nothing
                factor=1
            sorted_plants.append({
                "cost" : round(cost_per_pwh,1),
                "name" : powerplant["name"],
                "pmin" : round(powerplant["pmin"]*factor,1),
                "pmax" : round(powerplant["pmax"]*factor,1)
            })
        sorted_plants.sort(key=itemgetter("cost"))
        return(sorted_plants)

    def generate_power(self,order):
        """
        generates the final solution after pre treatment
        :param order: list of plants ordered by cost
        :return: dict containing each plant and the power it generates
        """
        res=list() #contains final result
        temp_min=dict() #contains a simplified dict to compare with the pmin values
        current_load=self.load #contains the amount of energy still to produce
        i=0 #contains the index of the current powerplant in order list
        finish=False # flags if the solver is done

        for powerplant in order:
            if current_load>0:
                # Check if max can be added
                if powerplant["pmax"]<= current_load:
                    # Check if, by adding max, the next plant will have enough space for its min
                    if powerplant["pmax"]+self.load-current_load+ order[i+1]["pmin"] >self.load and powerplant["pmax"]-order[i+1]["pmin"]>=powerplant["pmin"]:
                        # If not, we add enough of it so next plant can add its pmin
                        value=current_load-order[i+1]["pmin"]
                    else:
                        # Else, we add the max
                        value=powerplant["pmax"]
                    res.append({
                        "name" : powerplant["name"],
                        "p" : value
                    })
                    temp_min[powerplant["name"]]=powerplant["pmin"]
                    current_load-=value
                else:
                    # If no room for max but enough room for min
                    if powerplant["pmin"]<=current_load:
                        #We add the remaining load
                        res.append({
                            "name" : powerplant["name"],
                            "p" : current_load
                        })
                        temp_min[powerplant["name"]] = powerplant["pmin"]
                        current_load -= powerplant["pmax"]
                    else:
                        #If not, optimizing the best way to finish the load
                        completing,overload,not_used = self.minimal_cost_remaining(order[order.index(powerplant)::],current_load)
                        i=-1
                        while overload>0:
                            # Once completed, we need to empty the load from previous plants if overloaded
                            temp_name=list(res[i].keys())[0]
                            temp_value=list(res[i].values())[0]
                            pmin=temp_min[temp_name]
                            substract=min(temp_value-pmin,overload)
                            res[i]={temp_name:round(temp_value-substract,1)} # Edit the value by substracting some of (or all) the overlaod
                            overload-=substract #decreasing the overload until it reaches 0
                        res.append(completing)
                        for plant in not_used:
                            #completing the solution with the unused plants
                            res.append({
                                "name" : plant['name'],
                                "p" : 0
                            })
                        current_load=0
                        finish=True
            else:
                res.append({
                    "name" : powerplant['name'],
                    "p" : 0
                })
            i+=1
        return(res)


    def minimal_cost_remaining(self,remaining_plants,current_load):
        """
        proposes a solution to finish the load without violating pmin and pmax constraint
        and trying to make it optimal
        :param remaining_plants: list of plants not used by the solver
        :param current_load: remaining load to produce
        :return:
        """
        for plant in remaining_plants:
            if plant["pmax"]>=current_load:
                # If the load can be achieved by the plant, we check how much it would cost, or we take the cost of the pmin
                plant["price_to_complete"]=round(max(current_load,plant["pmin"])*plant["cost"],1)
            else:
                # If the load cannot be achieved, we ignore the plant
                plant["price_to_complete"]=float("inf")

        remaining_plants.sort(key=itemgetter("price_to_complete"))

        use_plant=remaining_plants[0]
        value_completed=use_plant["pmin"]
        completing={use_plant["name"]:value_completed}
        overload=round(value_completed-current_load,1)
        not_used_plants=remaining_plants[1::]

        return completing,overload,not_used_plants

def solve(payload):
    solver=Process(payload)
    return solver.process()
