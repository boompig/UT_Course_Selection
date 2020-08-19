module.exports = {
    env: {
        browser: true,
        es2020: true,
    },
    extends: [
        'plugin:vue/essential',
        'airbnb-base',
    ],
    parserOptions: {
        ecmaVersion: 11,
    },
    plugins: [
        'vue',
    ],
    rules: {
        'no-plusplus': 0,
        indent: ['error', 4],
        'arrow-body-style': ['error', 'always'],
        'no-else-return': 0,
    },
};
