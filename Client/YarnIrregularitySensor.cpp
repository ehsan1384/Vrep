extern "C" {
    #include "extApi.h"
}
#include "YarnIrregularitySensor.hpp"
#include "VREPClient.hpp"

YarnIrregularitySensor::YarnIrregularitySensor(simxInt handle) :
    Object(handle),
    _detector(),
    _lastReading(),
    _rawDiameterMm(0.0),
    _rawFaultCode(0.0),
    _rawCvPercent(0.0)
{
}

void YarnIrregularitySensor::setDetectorConfig(const YarnIrregularityDetector::Config& config)
{
    _detector.setConfig(config);
}

void YarnIrregularitySensor::load(VREPClient& VREP)
{
    Object::load(VREP);
}

void YarnIrregularitySensor::update(VREPClient& VREP)
{
    VREP.readYarnSensorSignals(
        _name,
        _rawDiameterMm,
        _rawFaultCode,
        _rawCvPercent);

    _lastReading = _detector.processSample(_rawDiameterMm);

    if (_rawCvPercent > 0.0) {
        _lastReading.coefficientOfVariation = _rawCvPercent;
    }
    if (_rawFaultCode >= 0.0) {
        _lastReading.fault = static_cast<YarnIrregularityDetector::FaultType>(
            static_cast<int>(_rawFaultCode + 0.5));
    }
}

double YarnIrregularitySensor::readDiameterMm() const
{
    return _lastReading.diameterMm;
}

double YarnIrregularitySensor::readDeviationPercent() const
{
    return _lastReading.deviationPercent;
}

double YarnIrregularitySensor::readCoefficientOfVariation() const
{
    return _lastReading.coefficientOfVariation;
}

YarnIrregularityDetector::FaultType YarnIrregularitySensor::readFault() const
{
    return _lastReading.fault;
}

bool YarnIrregularitySensor::isYarnPresent() const
{
    return _lastReading.yarnPresent;
}

const YarnIrregularityDetector::Reading& YarnIrregularitySensor::getLastReading() const
{
    return _lastReading;
}

std::string YarnIrregularitySensor::signalName(const std::string& suffix) const
{
    return _name + suffix;
}
