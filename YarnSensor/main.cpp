#include <iostream>
#include <cstdio>
#include <cstdlib>
#include <signal.h>
#include <string.h>
#include <math.h>
#include <cassert>
#include "VREPClient.hpp"

static VREPClient VREP;

using namespace std;

static void exiting(bool success = true)
{
    VREP.stop();
    VREP.disconnect();
    if (success) {
        exit(EXIT_SUCCESS);
    } else {
        exit(EXIT_FAILURE);
    }
}

static void signal_handler(int sig, siginfo_t *siginfo, void *context)
{
    cout << endl << "Exiting..." << endl;
    exiting();
}

static void attachSignalHandler()
{
    struct sigaction action;
    bzero(&action, sizeof(action));
    action.sa_sigaction = &signal_handler;
    action.sa_flags = SA_SIGINFO;
    if (sigaction(SIGINT, &action, NULL) < 0) {
        cerr << "Unable to register signal handler" << endl;
        exit(EXIT_FAILURE);
    }
}

static void displayYarnSensors()
{
    size_t count = VREP.countYarnSensors();
    cout << "Registered yarn sensors: " << count << endl;
    for (size_t i = 0; i < count; i++) {
        const YarnIrregularitySensor& sensor = VREP.getYarnSensor(i);
        cout << "[" << i << "] " << sensor.getName() << endl;
    }
}

static void displayYarnReadings()
{
    for (size_t i = 0; i < VREP.countYarnSensors(); i++) {
        const YarnIrregularitySensor& sensor = VREP.getYarnSensor(i);
        cout << "   yarn[" << i << "] " << sensor.getName()
             << " diameter=" << sensor.readDiameterMm() << "mm"
             << " deviation=" << sensor.readDeviationPercent() << "%"
             << " CV=" << sensor.readCoefficientOfVariation() << "%"
             << " fault=" << YarnIrregularityDetector::faultTypeToString(sensor.readFault())
             << " present=" << (sensor.isYarnPresent() ? "yes" : "no")
             << endl;
    }
}

int main(int argc, char* argv[])
{
    int port = 0;
    char* ip = NULL;

    if (argc != 3) {
        cerr << "Usage: ./YarnSensor [ip address] [port number]" << endl;
        return EXIT_FAILURE;
    }
    ip = argv[1];
    port = atoi(argv[2]);

    attachSignalHandler();

    try {
        cout << "Connecting to V-REP server " << ip << ":" << port << endl;
        VREP.connect(ip, port);
        displayYarnSensors();

        YarnIrregularityDetector::Config config;
        config.nominalDiameterMm = 0.30;
        for (size_t i = 0; i < VREP.countYarnSensors(); i++) {
            VREP.getYarnSensor(i).setDetectorConfig(config);
        }

        cout << "Starting simulation" << endl;
        VREP.start();
        for (double t = 0; t < 60.0; t += 0.050) {
            cout << "Simulation step t=" << t << endl;
            displayYarnReadings();
            VREP.nextStep();
        }
        cout << "Stopping simulation" << endl;
        VREP.stop();
    } catch (string str) {
        cerr << "Exception error: " << str << endl;
        exiting(false);
    }

    exiting();
}
