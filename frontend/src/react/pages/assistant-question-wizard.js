export const ASSISTANT_OTHER_OPTION_VALUE = "__assistant_option_other__";
export const ASSISTANT_OTHER_OPTION_LABEL = "其他";

function isOtherOptionLabel(label) {
    const normalized = String(label || "").trim().toLowerCase();
    return normalized === "其他" || normalized === "other";
}

export function getQuestionKey(question, index) {
    const rawQuestion = typeof question?.question === "string" ? question.question.trim() : "";
    if (rawQuestion) {
        return rawQuestion;
    }
    return `question_${index + 1}`;
}

export function isOtherOptionValue(value) {
    return value === ASSISTANT_OTHER_OPTION_VALUE;
}

export function isOtherSelected(question, selectedValue) {
    if (question?.multiSelect) {
        return Array.isArray(selectedValue) && selectedValue.includes(ASSISTANT_OTHER_OPTION_VALUE);
    }
    return selectedValue === ASSISTANT_OTHER_OPTION_VALUE;
}

export function buildQuestionOptions(options) {
    const normalized = (Array.isArray(options) ? options : []).map((option, index) => {
        const label = option?.label || `选项 ${index + 1}`;
        const isOther = isOtherOptionLabel(label);
        return {
            ...option,
            label,
            value: isOther ? ASSISTANT_OTHER_OPTION_VALUE : label,
            isOther,
        };
    });

    const hasOtherOption = normalized.some((option) => option.isOther);
    if (!hasOtherOption) {
        normalized.push({
            label: ASSISTANT_OTHER_OPTION_LABEL,
            description: "若以上选项都不符合，可自行输入",
            value: ASSISTANT_OTHER_OPTION_VALUE,
            isOther: true,
        });
    }

    return normalized;
}

export function isQuestionAnswerReady(question, selectedValue, customValue) {
    const normalizedCustomValue = typeof customValue === "string" ? customValue.trim() : "";

    if (question?.multiSelect) {
        if (!Array.isArray(selectedValue) || selectedValue.length === 0) {
            return false;
        }
        if (!isOtherSelected(question, selectedValue)) {
            return true;
        }
        return normalizedCustomValue.length > 0;
    }

    if (!(typeof selectedValue === "string" && selectedValue.trim().length > 0)) {
        return false;
    }
    if (!isOtherSelected(question, selectedValue)) {
        return true;
    }
    return normalizedCustomValue.length > 0;
}

export function buildAnswersPayload(questions, questionAnswers, customAnswers) {
    const payload = {};
    const normalizedQuestions = Array.isArray(questions) ? questions : [];
    normalizedQuestions.forEach((question, index) => {
        const questionKey = getQuestionKey(question, index);
        const answerKey = question?.question || questionKey;
        const value = questionAnswers?.[questionKey];
        if (question?.multiSelect) {
            if (Array.isArray(value) && value.length > 0) {
                const normalizedValues = value
                    .map((item) => {
                        if (isOtherOptionValue(item)) {
                            return (customAnswers?.[questionKey] || "").trim();
                        }
                        return String(item || "").trim();
                    })
                    .filter(Boolean);
                if (normalizedValues.length > 0) {
                    payload[answerKey] = normalizedValues.join(", ");
                }
            }
            return;
        }
        if (typeof value === "string" && value.trim().length > 0) {
            const answerValue = isOtherOptionValue(value)
                ? (customAnswers?.[questionKey] || "").trim()
                : value.trim();
            if (answerValue) {
                payload[answerKey] = answerValue;
            }
        }
    });
    return payload;
}

export function getNextVisitedSteps(currentVisitedSteps, nextIndex) {
    return Array.from(
        new Set([...(Array.isArray(currentVisitedSteps) ? currentVisitedSteps : []), nextIndex])
    ).sort((a, b) => a - b);
}
