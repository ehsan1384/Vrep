#ifndef YARNIRREGULARITYDETECTOR_HPP
#define YARNIRREGULARITYDETECTOR_HPP

#include <deque>
#include <string>

/**
 * Offline/online yarn irregularity detector for weaving yarn.
 *
 * Measures diameter variation and classifies common textile faults:
 * thin place, thick place, nep (short thick fault), and yarn break.
 */
class YarnIrregularityDetector
{
    public:

        enum FaultType {
            FAULT_NONE = 0,
            FAULT_THIN = 1,
            FAULT_THICK = 2,
            FAULT_NEP = 3,
            FAULT_BREAK = 4
        };

        struct Config {
            double nominalDiameterMm;
            double thinRatio;
            double thickRatio;
            double nepRatio;
            double breakRatio;
            size_t historySize;
            size_t nepMaxSamples;

            Config();
        };

        struct Reading {
            double diameterMm;
            double deviationPercent;
            double coefficientOfVariation;
            FaultType fault;
            bool yarnPresent;

            Reading();
        };

        explicit YarnIrregularityDetector(const Config& config = Config());

        void setConfig(const Config& config);
        const Config& getConfig() const;

        Reading processSample(double diameterMm);

        double getLastDiameter() const;
        double getLastDeviationPercent() const;
        double getCoefficientOfVariation() const;
        FaultType getLastFault() const;
        bool isYarnPresent() const;

        static std::string faultTypeToString(FaultType fault);

    private:

        double computeCoefficientOfVariation() const;
        void pushHistory(double diameterMm);

        Config _config;
        std::deque<double> _history;
        double _lastDiameter;
        double _lastDeviation;
        double _lastCv;
        FaultType _lastFault;
        bool _yarnPresent;
        size_t _consecutiveThickSamples;
};

#endif
