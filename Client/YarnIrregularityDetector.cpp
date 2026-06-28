#include <cmath>
#include "YarnIrregularityDetector.hpp"

YarnIrregularityDetector::Config::Config() :
    nominalDiameterMm(0.30),
    thinRatio(0.75),
    thickRatio(1.35),
    nepRatio(1.80),
    breakRatio(0.20),
    historySize(100),
    nepMaxSamples(3)
{
}

YarnIrregularityDetector::Reading::Reading() :
    diameterMm(0.0),
    deviationPercent(0.0),
    coefficientOfVariation(0.0),
    fault(FAULT_NONE),
    yarnPresent(false)
{
}

YarnIrregularityDetector::YarnIrregularityDetector(const Config& config) :
    _config(config),
    _history(),
    _lastDiameter(0.0),
    _lastDeviation(0.0),
    _lastCv(0.0),
    _lastFault(FAULT_NONE),
    _yarnPresent(false),
    _consecutiveThickSamples(0)
{
}

void YarnIrregularityDetector::setConfig(const Config& config)
{
    _config = config;
    _history.clear();
    _consecutiveThickSamples = 0;
}

const YarnIrregularityDetector::Config& YarnIrregularityDetector::getConfig() const
{
    return _config;
}

YarnIrregularityDetector::Reading YarnIrregularityDetector::processSample(double diameterMm)
{
    Reading reading;
    reading.diameterMm = diameterMm;

    _lastDiameter = diameterMm;
    _yarnPresent = diameterMm >= (_config.nominalDiameterMm * _config.breakRatio);
    reading.yarnPresent = _yarnPresent;

    if (!_yarnPresent) {
        _lastFault = FAULT_BREAK;
        _lastDeviation = -100.0;
        _consecutiveThickSamples = 0;
        reading.fault = _lastFault;
        reading.deviationPercent = _lastDeviation;
        reading.coefficientOfVariation = computeCoefficientOfVariation();
        _lastCv = reading.coefficientOfVariation;
        return reading;
    }

    pushHistory(diameterMm);

    if (_config.nominalDiameterMm > 0.0) {
        _lastDeviation = ((diameterMm / _config.nominalDiameterMm) - 1.0) * 100.0;
    } else {
        _lastDeviation = 0.0;
    }

    const double nominal = _config.nominalDiameterMm;
    if (diameterMm < nominal * _config.thinRatio) {
        _lastFault = FAULT_THIN;
        _consecutiveThickSamples = 0;
    } else if (diameterMm > nominal * _config.nepRatio) {
        _consecutiveThickSamples++;
        if (_consecutiveThickSamples <= _config.nepMaxSamples) {
            _lastFault = FAULT_NEP;
        } else {
            _lastFault = FAULT_THICK;
        }
    } else if (diameterMm > nominal * _config.thickRatio) {
        _consecutiveThickSamples++;
        _lastFault = FAULT_THICK;
    } else {
        _consecutiveThickSamples = 0;
        _lastFault = FAULT_NONE;
    }

    _lastCv = computeCoefficientOfVariation();

    reading.deviationPercent = _lastDeviation;
    reading.coefficientOfVariation = _lastCv;
    reading.fault = _lastFault;
    return reading;
}

double YarnIrregularityDetector::getLastDiameter() const
{
    return _lastDiameter;
}

double YarnIrregularityDetector::getLastDeviationPercent() const
{
    return _lastDeviation;
}

double YarnIrregularityDetector::getCoefficientOfVariation() const
{
    return _lastCv;
}

YarnIrregularityDetector::FaultType YarnIrregularityDetector::getLastFault() const
{
    return _lastFault;
}

bool YarnIrregularityDetector::isYarnPresent() const
{
    return _yarnPresent;
}

std::string YarnIrregularityDetector::faultTypeToString(FaultType fault)
{
    switch (fault) {
        case FAULT_THIN:
            return "thin";
        case FAULT_THICK:
            return "thick";
        case FAULT_NEP:
            return "nep";
        case FAULT_BREAK:
            return "break";
        default:
            return "none";
    }
}

double YarnIrregularityDetector::computeCoefficientOfVariation() const
{
    if (_history.size() < 2) {
        return 0.0;
    }

    double mean = 0.0;
    for (size_t i = 0; i < _history.size(); i++) {
        mean += _history[i];
    }
    mean /= static_cast<double>(_history.size());

    if (mean <= 0.0) {
        return 0.0;
    }

    double variance = 0.0;
    for (size_t i = 0; i < _history.size(); i++) {
        double delta = _history[i] - mean;
        variance += delta * delta;
    }
    variance /= static_cast<double>(_history.size());

    return (sqrt(variance) / mean) * 100.0;
}

void YarnIrregularityDetector::pushHistory(double diameterMm)
{
    _history.push_back(diameterMm);
    while (_history.size() > _config.historySize) {
        _history.pop_front();
    }
}
