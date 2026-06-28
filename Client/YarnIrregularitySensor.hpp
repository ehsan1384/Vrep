#ifndef YARNIRREGULARITYSENSOR_HPP
#define YARNIRREGULARITYSENSOR_HPP

#include <string>
#include "Object.hpp"
#include "YarnIrregularityDetector.hpp"

class VREPClient;

/**
 * V-REP weaving yarn irregularity sensor.
 *
 * Reads diameter and fault signals published by the companion Lua child script.
 */
class YarnIrregularitySensor : public Object
{
    public:

        YarnIrregularitySensor(simxInt handle);

        void setDetectorConfig(const YarnIrregularityDetector::Config& config);

        void load(VREPClient& VREP);
        void update(VREPClient& VREP);

        double readDiameterMm() const;
        double readDeviationPercent() const;
        double readCoefficientOfVariation() const;
        YarnIrregularityDetector::FaultType readFault() const;
        bool isYarnPresent() const;

        const YarnIrregularityDetector::Reading& getLastReading() const;

    private:

        std::string signalName(const std::string& suffix) const;

        YarnIrregularityDetector _detector;
        YarnIrregularityDetector::Reading _lastReading;
        double _rawDiameterMm;
        double _rawFaultCode;
        double _rawCvPercent;
};

#endif
