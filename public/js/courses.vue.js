/* global Vue */
/* exported app */

const app = new Vue({
    el: '#app',
    data: {
        courses: [],
        coursesLoaded: false,
        coursesError: null,
        offerings: [],
        offeringsLoaded: false,
        offeringsError: null,

        // computed
        breadthReqs: [],
        breadthReqMap: {},
        distributionReqs: [],
        distributionReqMap: {},
        searchResults: [],
        searchType: null,
        searchString: null,

        // model - selected by user
        breadthReq: '',
        distributionReq: '',

        // visual
        showTab: 'breadth',
    },
    methods: {
        selectTab(type) {
            this.showTab = type;
        },
        getDistributionReqMap() {
            const start = 'This is a '.length;
            const reqs = this.courses.map((course) => {
                let s = course.DistributionRequirementStatus;
                if (s) {
                    s = s.substr(start);
                    const end = s.indexOf(' course');
                    s = s.substr(0, end);
                }
                return s;
            }).map((req) => {
                if (req) {
                    return req.split(' or ').filter((r) => {
                        return r && r !== 'TBA' && r !== 'None';
                    });
                } else {
                    return [];
                }
            });

            const reqMap = {};
            for (let i = 0; i < this.courses.length; i++) {
                const course = this.courses[i];
                for (let j = 0; j < reqs[i].length; j++) {
                    const req = reqs[i][j];
                    if (!(req in reqMap)) {
                        reqMap[req] = [];
                    }
                    reqMap[req].push(course);
                }
            }

            return reqMap;
        },
        getDistributionReqs() {
            this.distributionReqMap = this.getDistributionReqMap();
            const distributionReqs = Object.keys(this.distributionReqMap);
            distributionReqs.sort();
            return distributionReqs;
        },
        getBreadthReqMap() {
            const reqs = this.courses.map((course) => {
                if (course.BreadthRequirement) {
                    return course.BreadthRequirement.split(' + ').map((req) => {
                        return req.trim();
                    }).filter((req) => {
                        return req && req !== 'None' && req !== 'TBA';
                    });
                } else {
                    return [];
                }
            });

            const d = {};
            for (let i = 0; i < this.courses.length; i++) {
                const course = this.courses[i];
                const requirements = reqs[i];
                for (let j = 0; j < requirements.length; j++) {
                    const req = requirements[j];
                    if (!(req in d)) {
                        d[req] = [];
                    }
                    d[req].push(course);
                }
            }

            return d;
        },
        /**
         * @param {string} s
         * @returns {number}
         */
        getBreadthReqsNumber(s) {
            const match = s.match(/\((\d+)\)/);
            return Number.parseInt(match[1], 10);
        },
        /**
         * Breadth requirements are not normalized in the database
         * So have to normalize them here
         */
        getBreadthReqs() {
            this.breadthReqMap = this.getBreadthReqMap();
            const breadthRequirements = Object.keys(this.breadthReqMap);
            const d = {};
            breadthRequirements.forEach((s) => {
                d[s] = this.getBreadthReqsNumber(s);
            });
            breadthRequirements.sort((a, b) => { return d[a] - d[b]; });
            return breadthRequirements;
        },
        async getCourses() {
            const r = await window.fetch('/api/courses');
            if (r.ok) {
                this.coursesLoaded = true;
                this.coursesError = null;
                const courses = await r.json();
                this.courses = courses.sort((a, b) => {
                    if (a.code > b.code) {
                        return 1;
                    } else if (a.code < b.code) {
                        return -1;
                    } else {
                        return 0;
                    }
                });

                this.breadthReqs = this.getBreadthReqs();
                this.distributionReqs = this.getDistributionReqs();
            } else {
                this.coursesLoaded = false;
                this.coursesError = await r.body();
                this.courses = [];

                this.breadthReqs = [];
            }
        },
        async getOfferings() {
            const r = await window.fetch('/api/offerings');
            if (r.ok) {
                this.offeringsLoaded = true;
                this.offeringsError = null;
                this.offerings = await r.json();
            } else {
                this.offeringsLoaded = false;
                this.offeringsError = await r.body();
                this.offerings = [];
            }
        },
        searchByBreadthReq() {
            // search using the currently-selected breadth requirement
            // NOTE: breadthReqMap is already sorted by course code
            this.searchResults = this.breadthReqMap[this.breadthReq];
            this.searchType = 'Breadth Requirement';
            this.searchString = this.breadthReq;
        },
        searchByDistributionReq() {
            // search using the currently-selected breadth requirement
            // NOTE: distributionReqMap is already sorted by course code
            this.searchResults = this.distributionReqMap[this.distributionReq];
            this.searchType = 'Distribution Requirement';
            this.searchString = this.distributionReq;
        },
    },
    beforeMount() {
    // async
        this.getCourses();

        // async
        this.getOfferings();
    },
});
