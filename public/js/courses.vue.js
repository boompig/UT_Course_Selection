/**
 * Vue.js v3
 */


const app = new Vue({
    el: "#app",
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

        // model - selected by user
        breadthReq: "",
        distributionReq: "",
    },
    methods: {
        getDistributionReqMap: function() {
            const start = "This is a ".length;
            const reqs = this.courses.map((course) => {
                let s = course.DistributionRequirementStatus;
                if(s) {
                    s = s.substr(start);
                    let end = s.indexOf(" course");
                    s = s.substr(0, end);
                }
                return s;
            }).map((req) => {
                if(req) {
                    return req.split(" or ").filter((req) => {
                        return req && req !== "TBA" && req !== "None";
                    });
                } else {
                    return [];
                }
            });

            let reqMap = {};
            for(let i = 0; i < this.courses.length; i++) {
                let course = this.courses[i];
                for(let j = 0; j < reqs[i].length; j++) {
                    let req = reqs[i][j];
                    if(!(req in reqMap)) {
                        reqMap[req] = [];
                    }
                    reqMap[req].push(course);
                }
            }

            return reqMap;
        },
        getDistributionReqs: function() {
            this.distributionReqMap = this.getDistributionReqMap();
            return Object.keys(this.distributionReqMap);
        },
        getBreadthReqMap: function() {
            const reqs = this.courses.map((course) => {
                if(course.BreadthRequirement) {
                    return course.BreadthRequirement.split(" + ").map(req => {
                        return req.trim();
                    }).filter(req => {
                        return req && req !== "None" && req !== "TBA";
                    });
                } else {
                    return [];
                }
            });

            const d = {};
            for(let i = 0; i < this.courses.length; i++) {
                let course = this.courses[i];
                let requirements = reqs[i];
                for(let j = 0; j < requirements.length; j++) {
                    let req = requirements[j];
                    if(!(req in d)) {
                        d[req] = []
                    }
                    d[req].push(course);
                }
            }

            return d;
        },
        /**
         * Breadth requirements are not normalized in the database
         * So have to normalize them here
         */
        getBreadthReqs: function() {
            this.breadthReqMap = this.getBreadthReqMap();
            return Object.keys(this.breadthReqMap);
        },
        getCourses: async function() {
            const r = await window.fetch("/api/courses");
            if(r.ok) {
                this.coursesLoaded = true;
                this.coursesError = null;
                this.courses = await r.json();

                this.breadthReqs = this.getBreadthReqs();
                this.distributionReqs = this.getDistributionReqs();
            } else {
                this.coursesLoaded = false;
                this.coursesError = await r.body();
                this.courses = [];

                this.breadthReqs = [];
            }
        },
        getOfferings: async function() {
            const r = await window.fetch("/api/offerings");
            if(r.ok) {
                this.offeringsLoaded = true;
                this.offeringsError = null;
                this.offerings = await r.json();
            } else {
                this.offeringsLoaded = false;
                this.offeringsError = await r.body();
                this.offerings = [];
            }
        },
        searchByBreadthReq: function() {
            // search using the currently-selected breadth requirement
            this.searchResults = this.breadthReqMap[this.breadthReq];
            this.searchResults.sort((a, b) => {
                return a.code > b.code;
            });
        },
        searchByDistributionReq: function() {
            // search using the currently-selected breadth requirement
            this.searchResults = this.distributionReqMap[this.distributionReq];
            this.searchResults.sort((a, b) => {
                return a.code > b.code;
            });
        }
    },
    beforeMount() {
        // async
        this.getCourses();

        // async
        this.getOfferings();
    },
});