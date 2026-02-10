import test from "node:test";
import assert from "node:assert/strict";

import {
    ASSISTANT_OTHER_OPTION_VALUE,
    getQuestionKey,
    buildQuestionOptions,
    isQuestionAnswerReady,
    buildAnswersPayload,
    getNextVisitedSteps,
} from "../src/react/pages/assistant-question-wizard.js";

const questions = [
    {
        header: "选择项目",
        question: "你想基于哪个项目继续？",
        multiSelect: false,
        options: [{ label: "test" }, { label: "创建新项目" }, { label: "其他" }],
    },
    {
        header: "视频内容",
        question: "你想制作什么内容？",
        multiSelect: true,
        options: [{ label: "使用已有素材" }, { label: "我来描述内容" }, { label: "其他" }],
    },
];

test("buildQuestionOptions should normalize and keep a stable other value", () => {
    const normalized = buildQuestionOptions(questions[0].options);
    assert.equal(normalized[2].value, ASSISTANT_OTHER_OPTION_VALUE);
});

test("isQuestionAnswerReady should validate single and multi question answers", () => {
    const q1 = questions[0];
    const q2 = questions[1];
    const q1Key = getQuestionKey(q1, 0);
    const q2Key = getQuestionKey(q2, 1);

    assert.equal(isQuestionAnswerReady(q1, "", ""), false);
    assert.equal(isQuestionAnswerReady(q1, "test", ""), true);
    assert.equal(isQuestionAnswerReady(q1, ASSISTANT_OTHER_OPTION_VALUE, ""), false);
    assert.equal(isQuestionAnswerReady(q1, ASSISTANT_OTHER_OPTION_VALUE, "自定义项目"), true);

    assert.equal(isQuestionAnswerReady(q2, [], ""), false);
    assert.equal(isQuestionAnswerReady(q2, ["使用已有素材"], ""), true);
    assert.equal(isQuestionAnswerReady(q2, [ASSISTANT_OTHER_OPTION_VALUE], ""), false);
    assert.equal(isQuestionAnswerReady(q2, [ASSISTANT_OTHER_OPTION_VALUE], "自定义内容"), true);

    assert.equal(q1Key.length > 0, true);
    assert.equal(q2Key.length > 0, true);
});

test("buildAnswersPayload should map other values to custom text", () => {
    const questionAnswers = {
        [getQuestionKey(questions[0], 0)]: ASSISTANT_OTHER_OPTION_VALUE,
        [getQuestionKey(questions[1], 1)]: ["使用已有素材", ASSISTANT_OTHER_OPTION_VALUE],
    };
    const customAnswers = {
        [getQuestionKey(questions[0], 0)]: "我的旧项目",
        [getQuestionKey(questions[1], 1)]: "补充镜头需求",
    };
    const payload = buildAnswersPayload(questions, questionAnswers, customAnswers);

    assert.deepEqual(payload, {
        "你想基于哪个项目继续？": "我的旧项目",
        "你想制作什么内容？": "使用已有素材, 补充镜头需求",
    });
});

test("getNextVisitedSteps should keep unique and sorted visited indexes", () => {
    assert.deepEqual(getNextVisitedSteps([0], 1), [0, 1]);
    assert.deepEqual(getNextVisitedSteps([0, 1], 1), [0, 1]);
    assert.deepEqual(getNextVisitedSteps([0, 2], 1), [0, 1, 2]);
});
