-- Yarn irregularity sensor simulation for V-REP / CoppeliaSim
-- Attach as child script to a proximity sensor named "yarnSensor*"
--
-- Scene setup:
-- 1. Create a cylinder shape named "yarn" (moving along X axis).
-- 2. Add a ray proximity sensor named "yarnSensor_main" aligned with yarn path.
-- 3. Attach this script to the sensor object.

sim=require'sim'

-- Sensor configuration
local sensorName=sim.getObjectName(sim.getObjectAssociatedWithScript())
local nominalDiameter=0.30 -- mm
local thinRatio=0.75
local thickRatio=1.35
local nepRatio=1.80
local breakRatio=0.20
local historySize=100
local nepMaxSamples=3

local yarnHandle=sim.getObjectHandle('yarn')
local history={}
local consecutiveThick=0

local function pushHistory(value)
    table.insert(history,value)
    while #history>historySize do
        table.remove(history,1)
    end
end

local function computeCV()
    if #history<2 then
        return 0.0
    end
    local mean=0.0
    for i=1,#history do
        mean=mean+history[i]
    end
    mean=mean/#history
    if mean<=0.0 then
        return 0.0
    end
    local variance=0.0
    for i=1,#history do
        local d=history[i]-mean
        variance=variance+d*d
    end
    variance=variance/#history
    return (math.sqrt(variance)/mean)*100.0
end

local function classifyFault(diameter)
    if diameter<nominalDiameter*breakRatio then
        consecutiveThick=0
        return 4 -- break
    end
    if diameter<nominalDiameter*thinRatio then
        consecutiveThick=0
        return 1 -- thin
    end
    if diameter>nepRatio*nominalDiameter then
        consecutiveThick=consecutiveThick+1
        if consecutiveThick<=nepMaxSamples then
            return 3 -- nep
        end
        return 2 -- thick
    end
    if diameter>thickRatio*nominalDiameter then
        consecutiveThick=consecutiveThick+1
        return 2 -- thick
    end
    consecutiveThick=0
    return 0 -- none
end

local function readYarnDiameter()
  -- Simulated optical shadow measurement from cylinder radius.
  local sx,sy,sz=sim.getObjectSize(yarnHandle)
  local diameter=math.max(sy,sz)*1000.0 -- meters to mm
  return diameter
end

function sysCall_init()
    sim.setFloatSignal(sensorName..'_diameter',nominalDiameter)
    sim.setFloatSignal(sensorName..'_fault',0)
    sim.setFloatSignal(sensorName..'_cv',0)
end

function sysCall_sensing()
    local diameter=readYarnDiameter()
    pushHistory(diameter)
    local fault=classifyFault(diameter)
    local cv=computeCV()

    sim.setFloatSignal(sensorName..'_diameter',diameter)
    sim.setFloatSignal(sensorName..'_fault',fault)
    sim.setFloatSignal(sensorName..'_cv',cv)
end
